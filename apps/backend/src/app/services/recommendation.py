"""Recommendation orchestration service (F17).

Owner: Zhou (backend)
Feature ID: F17 (api endpoints)

Wires the pipeline: resolver (F12) → engine (F06–F11) → LLM advisor (F16)
→ persist (advise_run + proposal) → return Recommendation.

Persistence is best-effort: a DB failure is logged but never blocks the
response (§3.4 / AC7).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.adapters.llm.base import AdvisorLLM, assert_numbers_grounded
from app.adapters.llm.factory import make_advisor
from app.adapters.resolver import Resolver
from app.core.config import Settings, get_settings
from app.domain.models import CarType, Household, Recommendation

logger = logging.getLogger(__name__)

# An existing heat pump is treated as "ageing" (a replacement-worthy efficiency
# upgrade) above this age, mirroring the Layer-3 Case-B threshold documented on
# Household.existing_heatpump_year in models.py.
_AGEING_HEATPUMP_YEARS = 12
_AGEING_HEATPUMP_SCOP = 3.0


def _household_context(household: Household) -> dict[str, str]:
    """Qualitative description of the household's current situation for the LLM.

    This is prose-grounding context only — it lets the advisor reason about WHY
    an upgrade fits (e.g. "your 2009 heat pump is ageing, so a replacement
    qualifies for the KfW efficiency subsidy") rather than just restating the
    saving figure.  Deliberately carries NO € amounts: the number-assertion
    guard (§15) only validates €-prefixed tokens, so keeping money out of here
    means the guard stays strict on the computed payload figures.
    """
    ctx: dict[str, str] = {}

    ctx["building"] = (
        f"{household.floor_area_m2} m² home built {household.building_year}, "
        f"{household.occupants} occupant(s)"
    )
    ctx["heating"] = f"currently heats with {household.heating.fuel.value.lower()}"

    if household.existing_heatpump_year is not None:
        parts = [f"existing heat pump installed {household.existing_heatpump_year}"]
        if household.existing_heatpump_scop is not None:
            parts.append(f"SCOP {household.existing_heatpump_scop:g}")
        if household.existing_heatpump_power_kw is not None:
            parts.append(f"{household.existing_heatpump_power_kw:g} kW")
        age = datetime.now().year - household.existing_heatpump_year
        is_ageing = age >= _AGEING_HEATPUMP_YEARS or (
            household.existing_heatpump_scop is not None
            and household.existing_heatpump_scop < _AGEING_HEATPUMP_SCOP
        )
        verdict = (
            "ageing/inefficient — replacing it qualifies for the KfW efficiency subsidy"
            if is_ageing
            else "modern and efficient"
        )
        ctx["existing_heat_pump"] = f"{', '.join(parts)} ({verdict})"

    if household.existing_pv_kwp:
        ctx["existing_solar"] = f"{household.existing_pv_kwp:g} kWp PV already installed"
    if household.existing_battery_kwh:
        ctx["existing_battery"] = (
            f"{household.existing_battery_kwh:g} kWh battery already installed"
        )

    if household.existing_ev or household.mobility.kind == CarType.EV:
        charger = "with a home wallbox" if household.existing_ev_charger else "no home wallbox yet"
        ctx["mobility"] = f"already drives an EV ({charger})"
    elif household.mobility.kind == CarType.NONE:
        ctx["mobility"] = "no car"
    else:
        km = household.mobility.km_month
        km_str = f", ~{km:g} km/mo" if km else ""
        ctx["mobility"] = f"drives a {household.mobility.kind.value.lower()} car{km_str}"

    return ctx


class RecommendationService:
    """Top-level use case behind POST /api/v1/advisor/recommend.

    Orchestration order (§2 pipeline):
      1. resolver.resolve_pricing(plz)          → PricingContext + assumptions
      2. engine.recommend(household, ctx)        → Recommendation (raises NIE until F06-F11)
      3. make_advisor(settings).explain(payload) → fills explanation_md / proposal_copy_md
      4. assert_numbers_grounded guard           → rejects hallucinated figures
      5. persist advise_run + proposal            → best-effort, never blocks
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resolver = Resolver(settings=self._settings)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        household: Household,
        specific_yield: float | None = None,
    ) -> Recommendation:
        """Resolve context, run the engine, explain, persist, return."""
        ctx, assumptions = self._resolver.resolve_pricing(household.plz)

        # Override specific yield if provided (e.g. from PVGIS adapter)
        if specific_yield is not None:
            from app.domain.models import Assumption

            assumptions.append(
                Assumption(
                    field="specific_yield_kwh_per_kwp",
                    value=f"{specific_yield} kWh/kWp",
                    source="PVGIS adapter",
                    editable=True,
                )
            )

        # Layer 5: resolve the live subsidy catalog (KfW/BAFA/VAT), mirroring the
        # resolver→PricingContext pattern. Offline-safe — falls back to seed rows
        # when Supabase is unconfigured, so the engine's KfW rate is data-driven.
        from app.domain.savings.subsidy_layer.catalog import resolve_subsidies

        subsidies = resolve_subsidies(
            supabase_url=self._settings.supabase_url,
            supabase_key=self._settings.supabase_service_role_key,
        )

        # Engine call — pure F06-F11 ladder (resolver-injected ctx, zero I/O).
        from app.domain.savings.engine import recommend

        rec: Recommendation = recommend(household, ctx, subsidies=subsidies)

        # ── LLM advisor + number guard ──────────────────────────────────
        advisor: AdvisorLLM = make_advisor(self._settings)
        payload = rec.model_dump()
        # Qualitative situation context so the advisor can reason about WHY the
        # upgrade fits this household (e.g. replacing an ageing heat pump for the
        # subsidy), not just restate the figure.  Strings only → guard unaffected.
        payload["household_context"] = _household_context(household)
        locale = household.locale
        copy = advisor.explain(payload, locale)

        # Number-assertion guard (§15): already applied inside explain(),
        # but we double-check here and fall back to the stub if needed.
        all_text = " ".join(str(v) for v in copy.values())
        if not assert_numbers_grounded(all_text, payload):
            logger.error("LLM advisor emitted ungrounded figure — using stub fallback")
            from app.adapters.llm.stub import StubAdvisor

            copy = StubAdvisor().explain(payload, locale)

        # Overlay LLM tier rationales (qualitative, no € — the card shows figures).
        # Falls through to the deterministic F27 template text when a key is absent
        # (e.g. stub fallback or guard rejection), so cards always have copy.
        new_tiers = [
            tier.model_copy(
                update={
                    "rationale_md": copy.get(f"tier_rationale_{tier.id}", tier.rationale_md),
                }
            )
            for tier in rec.tiers
        ]

        rec = rec.model_copy(
            update={
                "explanation_md": copy.get("explanation_md", rec.explanation_md),
                "proposal_copy_md": copy.get("proposal_copy_md", rec.proposal_copy_md),
                "tiers": new_tiers,
                "upsell": rec.upsell.model_copy(
                    update={"reason_md": copy.get("upsell_reason_md", rec.upsell.reason_md)}
                ),
            }
        )

        # ── Best-effort persistence ─────────────────────────────────────
        self._persist(household=household, rec=rec)

        return rec

    # ------------------------------------------------------------------
    # Persistence (best-effort — never blocks on DB failure, AC7)
    # ------------------------------------------------------------------

    def _persist(self, household: Household, rec: Recommendation) -> None:
        if not self._settings.supabase_url or not self._settings.supabase_service_role_key:
            logger.debug("No DB configured — skipping persistence")
            return
        try:
            from app.adapters.supabase import get_supabase_client

            with get_supabase_client(self._settings) as client:
                # Insert advise_run
                run_body: dict[str, Any] = {
                    "household_json": household.model_dump(),
                    "options_json": {},
                    "recommendation_json": rec.model_dump(),
                }
                run_resp = client.post(
                    "/advise_run",
                    json=run_body,
                    headers={"Prefer": "return=representation"},
                )
                if run_resp.status_code in (200, 201):
                    run_rows = run_resp.json()
                    if run_rows:
                        run_id = run_rows[0]["id"]
                        # Insert proposal
                        client.post(
                            "/proposal",
                            json={
                                "advise_run_id": run_id,
                                "copy_md": rec.proposal_copy_md,
                            },
                        )
        except Exception:
            logger.warning("Persistence failed (best-effort; continuing)", exc_info=True)