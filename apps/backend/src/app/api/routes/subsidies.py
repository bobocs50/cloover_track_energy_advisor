"""Subsidy layer API — live federal subsidy catalog with automatic refresh.

GET  /api/v1/advisor/subsidies         → current catalog rows + example grants
POST /api/v1/advisor/subsidies/refresh → run the Tavily+OpenAI crawler now
"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings
from app.domain.savings.subsidy_layer.catalog import resolve_subsidies
from app.domain.savings.subsidy_layer.crawler import refresh_federal

router = APIRouter(prefix="/api/v1/advisor", tags=["subsidies"])

# Example capex values for the GET response — illustrate what grants look like
# for a typical household (Berlin, balanced solar bundle + heat pump + EV).
_EXAMPLE_CAPEX: dict[str, float] = {
    "heat_pump_a": 22000.0,
    "heat_pump_b": 22000.0,
    "pv": 15000.0,
    "battery": 5600.0,
    "ev_charger": 1200.0,
}


@router.get("/subsidies")
def get_subsidies() -> dict[str, Any]:
    """Current subsidy catalog — all eligible rows + example grants.

    Reads the date-gated subsidy_catalog table. Falls back to the offline seed
    if Supabase is unavailable. Returns:
    - rows: all currently-eligible subsidy rows
    - example_grants: illustrative grant amounts for a typical bundle
    - verified_at: when the seed/crawl last wrote these rows
    """
    settings = get_settings()
    ctx = resolve_subsidies(
        request_date=date.today(),
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )

    rows = []
    for component, subsidies in ctx.by_component.items():
        for s in subsidies:
            rows.append({
                "programme": s.programme,
                "component": component,
                "rate": s.rate,
                "rate_pct": f"{s.rate * 100:.0f}%",
                "cap_eur": s.cap_eur,
                "source_url": s.source_url,
                "valid_from": s.valid_from.isoformat(),
                "valid_until": s.valid_until.isoformat() if s.valid_until else None,
                "notes": s.notes,
            })

    example_grants: dict[str, Any] = {}
    for component, capex in _EXAMPLE_CAPEX.items():
        grant = ctx.compute_grant(component, capex)
        if ctx.for_component(component):  # only show components with at least one row
            example_grants[component] = {
                "example_capex_eur": capex,
                "grant_eur": grant,
                "capex_after_subsidy_eur": round(capex - grant, 2),
                "assumptions": ctx.applied_assumptions(component),
            }

    return {
        "rows": rows,
        "total_rows": len(rows),
        "example_grants": example_grants,
        "request_date": date.today().isoformat(),
        "note": "Rates sourced from official federal pages. Crawled weekly. Demo: run POST /refresh to verify live.",
    }


@router.post("/subsidies/refresh")
def refresh_subsidies() -> dict[str, Any]:
    """Run the federal subsidy crawler now — Tavily fetch → OpenAI extract → gate → Supabase.

    Promoted rows go live immediately (engine reads them on the next request).
    Suspicious rows (rate jumped > 25%) go to subsidy_catalog_staging for review.
    Returns counts and timestamp for the demo chip.
    """
    settings = get_settings()
    result = refresh_federal(
        tavily_key=settings.tavily_api_key,
        openai_key=settings.openai_api_key,
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )

    status = "✅ all sources processed" if result.errors == 0 else f"⚠️ {result.errors} source(s) failed"
    if result.promoted == 0 and result.errors > 0:
        status = "❌ crawler unavailable (check API keys)"

    return {
        **result.as_dict(),
        "status": status,
        "message": (
            f"Refreshed {result.promoted} federal subsidy rows. "
            f"{result.quarantined} quarantined (rate change too large). "
            f"{result.errors} errors."
        ),
    }
