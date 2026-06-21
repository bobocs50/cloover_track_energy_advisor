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
from typing import Any

from app.adapters.llm.base import AdvisorLLM, assert_numbers_grounded
from app.adapters.llm.factory import make_advisor
from app.adapters.resolver import Resolver
from app.core.config import Settings, get_settings
from app.domain.models import Household, Recommendation

logger = logging.getLogger(__name__)


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

        # Engine call — pure F06-F11 ladder (resolver-injected ctx, zero I/O).
        from app.domain.savings.engine import recommend

        rec: Recommendation = recommend(household, ctx)

        # ── LLM advisor + number guard ──────────────────────────────────
        advisor: AdvisorLLM = make_advisor(self._settings)
        payload = rec.model_dump()
        locale = household.locale
        copy = advisor.explain(payload, locale)

        # Number-assertion guard (§15): already applied inside explain(),
        # but we double-check here and fall back to the stub if needed.
        all_text = " ".join(str(v) for v in copy.values())
        if not assert_numbers_grounded(all_text, payload):
            logger.error("LLM advisor emitted ungrounded figure — using stub fallback")
            from app.adapters.llm.stub import StubAdvisor

            copy = StubAdvisor().explain(payload, locale)

        rec = rec.model_copy(
            update={
                "explanation_md": copy.get("explanation_md", rec.explanation_md),
                "proposal_copy_md": copy.get("proposal_copy_md", rec.proposal_copy_md),
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