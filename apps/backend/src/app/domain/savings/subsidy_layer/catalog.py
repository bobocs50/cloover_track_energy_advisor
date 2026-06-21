"""Subsidy catalog resolver — reads gated rows from Supabase, builds a SubsidyContext.

Mirrors the price_catalog → PricingContext pattern (F12). The financing engine (F11)
consumes SubsidyContext and enforces the KfW cap; it never imports a subsidy constant
directly (AC6). Offline-safe: with no Supabase configured we fall back to the same
six MVP rows the seed migration writes, so the demo runs with networking disabled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import httpx

# KfW 458 hard cap: combined rate for heat-pump funding may not exceed 70 %.
# This cap is heat-pump-specific — PV/battery/EV have their own programme limits.
KFW_MAX_RATE = 0.70
_KFW_COMPONENTS = {"heat_pump_a", "heat_pump_b"}


@dataclass(frozen=True)
class Subsidy:
    programme: str          # 'kfw_458_base', 'kfw_458_speed_bonus', 'vat_pv_battery', ...
    component: str          # 'heat_pump_a'|'heat_pump_b'|'pv'|'battery'|'ev_charger'
    rate: float             # fraction_of_capex
    cap_eur: float | None   # absolute grant cap; None = uncapped
    source_url: str
    valid_from: date
    valid_until: date | None
    notes: str = ""

    def as_assumption(self) -> dict[str, object]:
        """Cited Assumption entry for the response's assumptions[] array (R7)."""
        return {
            "label": f"{self.programme} ({self.component})",
            "rate": self.rate,
            "cap_eur": self.cap_eur,
            "source": self.source_url,
        }


@dataclass
class SubsidyContext:
    """All subsidies eligible for one request, grouped by component.

    Injected into the financing engine (F11) alongside PricingContext.
    The engine calls for_component() per product, then compute_grant() per capex item.
    """

    request_date: date
    by_component: dict[str, list[Subsidy]] = field(default_factory=dict)

    def for_component(self, component: str) -> list[Subsidy]:
        return self.by_component.get(component, [])

    def combined_rate(self, component: str) -> float:
        """Sum of eligible rates for a component.

        KfW 70% hard cap applies only to heat-pump components (§5.3).
        PV/battery/EV programmes have their own caps enforced via cap_eur.
        """
        total = sum(s.rate for s in self.for_component(component))
        if component in _KFW_COMPONENTS:
            return min(total, KFW_MAX_RATE)
        return total

    def compute_grant(self, component: str, capex_eur: float) -> float:
        """Grant for one component: rate-capped fraction of capex, then the absolute cap.

        cap_eur represents the programme-wide ceiling on the total combined grant
        (not a per-row cap), so we take max(caps) — the most generous ceiling
        across all applying rows — rather than min. F11 owns the canonical version.
        """
        rate = self.combined_rate(component)
        caps = [s.cap_eur for s in self.for_component(component) if s.cap_eur is not None]
        grant = rate * capex_eur
        if caps:
            grant = min(grant, max(caps))
        return round(grant, 2)

    def applied_assumptions(self, component: str) -> list[dict[str, object]]:
        """One cited Assumption per subsidy row (R7) for the API response.

        Includes zero-rate rows (VAT relief) as informational citations so the user
        sees the source for 0% VAT — they just show rate=0 with a clear label.
        """
        return [s.as_assumption() for s in self.for_component(component)]


# ── Offline fallback: identical to the seed migration rows (R9 / demo-safety). ─
def _fallback_rows() -> list[Subsidy]:
    kfw_url = (
        "https://www.kfw.de/inlandsfoerderung/Privatpersonen/Bestehende-Immobilie/"
        "F%C3%B6rderprodukte/Heizungsf%C3%B6rderung-f%C3%BCr-Privatpersonen-Wohngeb%C3%A4ude-(458)/"
    )
    ustg_url = "https://www.gesetze-im-internet.de/ustg_1980/__12.html"
    bafa_url = (
        "https://www.bafa.de/DE/Energie/Energieeffizienz/Elektromobilitaet/"
        "elektromobilitaet_node.html"
    )
    return [
        Subsidy("kfw_458_base", "heat_pump_a", 0.30, 21000.0, kfw_url,
                date(2026, 6, 20), None, "Grundförderung 30%."),
        Subsidy("kfw_458_base", "heat_pump_b", 0.30, 21000.0, kfw_url,
                date(2026, 6, 20), None, "Grundförderung 30% (Case B, no speed bonus)."),
        Subsidy("kfw_458_speed_bonus", "heat_pump_a", 0.20, 21000.0, kfw_url,
                date(2026, 6, 20), None, "Klima-Geschwindigkeitsbonus 20% — Case A only."),
        Subsidy("vat_pv_battery", "pv", 0.00, None, ustg_url,
                date(2026, 6, 20), None, "0% VAT (§12(3) UStG); price already net."),
        Subsidy("vat_pv_battery", "battery", 0.00, None, ustg_url,
                date(2026, 6, 20), None, "0% VAT (§12(3) UStG) incl. added battery."),
        Subsidy("bafa_ev_umweltbonus", "ev_charger", 0.00, 0.0, bafa_url,
                date(2020, 1, 1), date(2023, 12, 17), "Umweltbonus ended 17 Dec 2023."),
    ]


def _is_eligible(row: Subsidy, on: date) -> bool:
    """valid_from ≤ today AND (valid_until IS NULL OR valid_until ≥ today) (R5/AC5)."""
    if row.valid_from > on:
        return False
    if row.valid_until is not None and row.valid_until < on:
        return False
    return True


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _rows_from_supabase(supabase_url: str, supabase_key: str) -> list[Subsidy] | None:
    """Fetch all catalog rows from Supabase. Returns None on any failure."""
    if not supabase_url or not supabase_key:
        return None
    try:
        resp = httpx.get(
            f"{supabase_url.rstrip('/')}/rest/v1/subsidy_catalog",
            params={"select": "*"},
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
            },
            timeout=5,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None
        out: list[Subsidy] = []
        for r in rows:
            out.append(
                Subsidy(
                    programme=r["programme"],
                    component=r["component"],
                    rate=float(r["rate"]),
                    cap_eur=None if r.get("cap_eur") is None else float(r["cap_eur"]),
                    source_url=r["source_url"],
                    valid_from=_parse_date(r["valid_from"]),
                    valid_until=None if r.get("valid_until") is None else _parse_date(r["valid_until"]),
                    notes=r.get("notes") or "",
                )
            )
        return out
    except Exception:
        return None


def resolve_subsidies(
    request_date: date | None = None,
    *,
    supabase_url: str = "",
    supabase_key: str = "",
) -> SubsidyContext:
    """Build a SubsidyContext of all rows eligible on request_date, grouped by component.

    Reads Supabase; falls back to the offline seed if unavailable (R9/AC5 demo-safety).
    Expired rows (valid_until in the past) are excluded — gating is data, not logic.
    """
    on = request_date or date.today()
    rows = _rows_from_supabase(supabase_url, supabase_key)
    if rows is None:
        rows = _fallback_rows()

    by_component: dict[str, list[Subsidy]] = {}
    for row in rows:
        if _is_eligible(row, on):
            by_component.setdefault(row.component, []).append(row)
    return SubsidyContext(request_date=on, by_component=by_component)


def components_for_intake(
    *,
    wants_heatpump: bool = False,
    replaces_fossil_heating: bool = False,
    has_existing_heatpump: bool = False,
    wants_pv: bool = True,
    wants_battery: bool = True,
    wants_ev_charger: bool = True,
) -> list[str]:
    """Map household situation → catalog component keys it qualifies for.

    Heat-pump case breakdown (§5.3 / R4):
    - has_existing_heatpump=True → heat_pump_b (old HP → new HP; base 30% only, no speed bonus)
    - replaces_fossil_heating=True → heat_pump_a (fossil → HP; gets speed bonus 20%)
    - wants_heatpump=True only → heat_pump_a (new install, e.g. district heat / electric → HP)
    - none of the above → no heat pump component (household doesn't want one)
    """
    components: list[str] = []
    if has_existing_heatpump:
        components.append("heat_pump_b")
    elif replaces_fossil_heating or wants_heatpump:
        components.append("heat_pump_a")
    if wants_pv:
        components.append("pv")
    if wants_battery:
        components.append("battery")
    if wants_ev_charger:
        components.append("ev_charger")
    return components
