"""Site-Check adapter — permit & feasibility layer (F15).

Owner: Zhou (backend)
Feature ID: F15 (site check)

F15 IS THE PRODUCT'S SOLE PERMIT LAYER (R-F, §4).
It covers the full §4 scope:
  - Roof/PV verfahrensfrei (LBO)
  - Denkmalschutz gate (heritage)
  - GEG §71 compliance (heat pump)
  - WEG §20 / BGB §554 EV right
  - Grid registration notices (wallbox ≤11 kW notify / >11 kW approval)
  - Battery MaStR registration

Each §4 row produces exactly one FeasibilityFlag in the response regardless
of whether the rule is green / amber / info (AC8 — full permit scope enumerated).

OSM Overpass parking call is guarded; degrades to user checkbox (AC6).
MaStR / Denkmal seed values are used for demo PLZs; unknown elsewhere (§15).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.adapters.resolver import Resolver
from app.core.config import Settings, get_settings
from app.domain.models import (
    Assumption,
    EnergyContext,
    FeasibilityFlag,
    FeasibilityStatus,
    SiteCheckRequest,
    SiteCheckResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seeded Denkmal / MaStR data (mirrors seed.sql denkmal_seed / mastr_seed)
# ---------------------------------------------------------------------------
_DENKMAL_SEED: dict[str, bool] = {
    "10115": False,  # Berlin demo — not listed
    "80331": True,  # Munich demo — listed (triggers amber gate)
}

_MASTR_SEED: dict[str, int] = {
    "10115": 47,
    "80331": 63,
}


# ---------------------------------------------------------------------------
# OSM Overpass parking check (optional, falls back to checkbox)
# ---------------------------------------------------------------------------

_OSM_TIMEOUT: float = 5.0


def _check_parking_osm(lat: float, lon: float, radius_m: int = 50) -> str | None:
    """Query OSM Overpass for parking amenity near the address.

    Returns "private" if a driveway or garage is found nearby,
    "street" if only street parking, or None on failure (AC6).
    """
    query = (
        f"[out:json][timeout:5];"
        f"(node[amenity=parking](around:{radius_m},{lat},{lon});"
        f"way[amenity=parking](around:{radius_m},{lat},{lon}););"
        f"out tags 1;"
    )
    try:
        with httpx.Client(timeout=_OSM_TIMEOUT) as client:
            resp = client.get(
                "https://overpass-api.de/api/interpreter",
                params={"data": query},
            )
        if resp.status_code == 200:
            elements = resp.json().get("elements", [])
            for el in elements:
                access = el.get("tags", {}).get("access", "")
                parking_type = el.get("tags", {}).get("parking", "")
                if access == "private" or parking_type in ("garage", "carport"):
                    return "private"
            return "street"
    except Exception:
        logger.debug("OSM Overpass unavailable; using checkbox fallback", exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Site-Check runner
# ---------------------------------------------------------------------------


def run_site_check(
    req: SiteCheckRequest,
    *,
    denkmal_listed: bool | None = None,
    private_parking: bool | None = None,
    wallbox_kw: float = 11.0,
    has_battery: bool = True,
    has_oil_or_gas_heating: bool = True,
    settings: Settings | None = None,
) -> SiteCheckResponse:
    """Run the §4 site-check and return a typed SiteCheckResponse.

    Parameters
    ----------
    req:
        The SiteCheckRequest (address + plz + floor_area_m2 + building_year).
    denkmal_listed:
        Override heritage listing (True = listed → amber gate).
        None → reads from denkmal_seed / checkbox fallback.
    private_parking:
        Override parking type (True = private, False = street-only).
        None → tries OSM Overpass then checkbox fallback.
    wallbox_kw:
        Rated power of the wallbox in kW — drives ≤/>11 kW notice (AC5).
    has_battery:
        True if a battery is included — triggers the MaStR notice.
    has_oil_or_gas_heating:
        True if household has fossil heating — triggers HP ℹ️ advisory.
    settings:
        Optional Settings override.
    """
    resolved_settings = settings or get_settings()
    resolver = Resolver(settings=resolved_settings)

    # Resolve location context (lat/lon / specific_yield / retail_price etc.)
    loc, loc_assumptions = resolver.resolve_location(req.plz)

    assumptions: list[Assumption] = list(loc_assumptions)

    # ---- 1. Denkmalschutz (heritage) — the only real gate (§4) ----
    if denkmal_listed is None:
        denkmal_listed = _DENKMAL_SEED.get(req.plz)

    if denkmal_listed is None:
        # No seed data — label as checkbox fallback
        denkmal_listed = False
        assumptions.append(
            Assumption(
                field="denkmal_listed",
                value="not listed (checkbox fallback)",
                source=("No national Denkmal API; Bavaria WFS available as stretch (§4, §16 D7)"),
                editable=True,
            )
        )

    # ---- 2. MaStR neighbour count ----
    mastr_count: int | None = (
        loc.mastr_count if loc.mastr_count is not None else _MASTR_SEED.get(req.plz)
    )
    if mastr_count is None:
        assumptions.append(
            Assumption(
                field="mastr_neighbour_count",
                value="⚪ unknown",
                source=f"MaStR — no count for PLZ {req.plz}",
                editable=False,
            )
        )

    # ---- 3. Parking (EV) ----
    if private_parking is None:
        osm_result = _check_parking_osm(loc.lat, loc.lon)
        if osm_result is None:
            # OSM unavailable — assume private (AC6 checkbox fallback)
            private_parking = True
            assumptions.append(
                Assumption(
                    field="private_parking",
                    value="private (checkbox fallback)",
                    source="OSM Overpass unavailable; assumed private driveway/garage",
                    editable=True,
                )
            )
        else:
            private_parking = osm_result == "private"

    # ---- Build the six mandatory §4 permit flags (AC8) ----
    flags: list[FeasibilityFlag] = [
        _flag_pv_permit(),
        _flag_denkmal(denkmal_listed),
        _flag_hp_geg(has_oil_or_gas_heating),
        _flag_ev_right(private_parking),
        _flag_grid_registration(wallbox_kw),
        _flag_battery_mastr(has_battery),
    ]

    # MaStR social proof: always present as extra info (never gates, §4)
    flags.append(_flag_mastr_social_proof(mastr_count))

    # roof_ok: True unless heritage is listed (amber gate)
    roof_ok = not denkmal_listed

    energy_context = EnergyContext(
        lat=loc.lat,
        lon=loc.lon,
        specific_yield_kwh_per_kwp=loc.specific_yield,
        retail_price_eur_kwh=loc.retail_price,
        grid_fee_eur_kwh=loc.grid_fee,
        climate_zone=loc.climate_zone,
        mastr_neighbour_count=mastr_count,
    )

    return SiteCheckResponse(
        roof_ok=roof_ok,
        feasibility_flags=flags,
        energy_context=energy_context,
        assumptions=assumptions,
    )


# ---------------------------------------------------------------------------
# Per-product flag builders (one per §4 row — AC8)
# ---------------------------------------------------------------------------


def _flag_pv_permit() -> FeasibilityFlag:
    """Solar PV — verfahrensfrei (no permit needed, LBO)."""
    return FeasibilityFlag(
        product="Solar PV",
        check="Building permit (Baugenehmigung)",
        status=FeasibilityStatus.GREEN,
        message="Roof PV is verfahrensfrei — no permit needed (LBO)",
    )


def _flag_denkmal(denkmal_listed: bool) -> FeasibilityFlag:
    """Denkmalschutz — the only real gate (§4)."""
    if denkmal_listed:
        return FeasibilityFlag(
            product="Solar PV",
            check="Denkmalschutz (heritage listing)",
            status=FeasibilityStatus.AMBER,
            message=(
                "Denkmalschutz listed → Untere Denkmalschutzbehörde approval "
                "required before installation."
            ),
        )
    return FeasibilityFlag(
        product="Solar PV",
        check="Denkmalschutz (heritage listing)",
        status=FeasibilityStatus.GREEN,
        message="Not heritage listed — no Denkmalschutz restriction.",
    )


def _flag_hp_geg(has_old_heating: bool) -> FeasibilityFlag:
    """Heat pump — GEG §71 always compliant; old boiler ℹ️ if applicable."""
    if has_old_heating:
        return FeasibilityFlag(
            product="Heat pump",
            check="GEG §71 compliance + boiler replacement",
            status=FeasibilityStatus.INFO,
            message=(
                "GEG §71 compliant — air-source HP supplies ≥65 % renewables. "
                "Fossil boiler replacement qualifies for KfW 458 (up to 50 % grant, Case A)."
            ),
        )
    return FeasibilityFlag(
        product="Heat pump",
        check="GEG §71 compliance",
        status=FeasibilityStatus.GREEN,
        message=("GEG §71 compliant — air-source heat pump supplies ≥65 % renewables (always)."),
    )


def _flag_ev_right(private_parking: bool) -> FeasibilityFlag:
    """EV charger — legal right (WEG §20 / BGB §554) + parking context."""
    if private_parking:
        return FeasibilityFlag(
            product="EV charger",
            check="Right to install (WEG §20 / BGB §554)",
            status=FeasibilityStatus.GREEN,
            message=(
                "Legal right to install a wallbox (WEG §20 / BGB §554). "
                "Private driveway/garage available — home charging vs petrol."
            ),
        )
    return FeasibilityFlag(
        product="EV charger",
        check="Right to install (WEG §20 / BGB §554) — street-only parking",
        status=FeasibilityStatus.AMBER,
        message=(
            "Legal right confirmed (WEG §20 / §554 BGB), but street-only parking "
            "detected — EV Layer 4 uses public-charge pricing fallback (Case B, §5.4)."
        ),
    )


def _flag_grid_registration(wallbox_kw: float) -> FeasibilityFlag:
    """Grid registration notice — ≤11 kW notify / >11 kW approval (§4)."""
    if wallbox_kw > 11.0:
        return FeasibilityFlag(
            product="EV charger",
            check="Grid registration (>11 kW)",
            status=FeasibilityStatus.INFO,
            message=(
                "Wallbox >11 kW: Netzbetreiber approval required before grid "
                "connection (§19 NIV / VDE-AR-N 4100)."
            ),
        )
    return FeasibilityFlag(
        product="EV charger",
        check="Grid registration (≤11 kW)",
        status=FeasibilityStatus.INFO,
        message=(
            "Wallbox ≤11 kW: notify your Netzbetreiber before installation "
            "(Anmeldepflicht, §19 NIV / VDE-AR-N 4100)."
        ),
    )


def _flag_battery_mastr(has_battery: bool) -> FeasibilityFlag:
    """Battery — MaStR registration within 1 month (§4)."""
    if has_battery:
        return FeasibilityFlag(
            product="Battery",
            check="MaStR registration",
            status=FeasibilityStatus.INFO,
            message=(
                "Battery storage must be registered in MaStR within 1 month "
                "of commissioning (§5 MaStRV)."
            ),
        )
    return FeasibilityFlag(
        product="Battery",
        check="MaStR registration",
        status=FeasibilityStatus.GREEN,
        message="No battery — MaStR registration not required.",
    )


def _flag_mastr_social_proof(mastr_count: int | None) -> FeasibilityFlag:
    """MaStR neighbour count — social proof (never gates, §4)."""
    if mastr_count is None:
        return FeasibilityFlag(
            product="Solar PV",
            check="Neighbour precedent (MaStR)",
            status=FeasibilityStatus.INFO,
            message="⚪ Unknown — no MaStR data for this PLZ (social proof; never gates).",
        )
    if mastr_count >= 40:
        return FeasibilityFlag(
            product="Solar PV",
            check="Neighbour precedent (MaStR)",
            status=FeasibilityStatus.GREEN,
            message=(
                f"{mastr_count} PV systems already installed nearby (social proof — not a gate)."
            ),
        )
    return FeasibilityFlag(
        product="Solar PV",
        check="Neighbour precedent (MaStR)",
        status=FeasibilityStatus.AMBER,
        message=(
            f"{mastr_count} PV systems in this PLZ "
            "(social proof only — neighbourhood adoption is growing)."
        ),
    )


# ---------------------------------------------------------------------------
# Legacy class wrapper
# ---------------------------------------------------------------------------


class SiteCheck:
    """Validate a site for installation feasibility.

    Thin wrapper around ``run_site_check`` for backwards compatibility.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def run(self, req: SiteCheckRequest, **kwargs: Any) -> SiteCheckResponse:
        """Return a feasibility report for an address."""
        return run_site_check(req, settings=self._settings, **kwargs)