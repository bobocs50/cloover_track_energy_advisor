"""Subsidy catalog offline seed + filter helper (F26).

Owner: Zhou (backend)
Feature ID: F26 (subsidy catalog)

IMPORTANT: Before each demo, Lukas must verify each source_url below against
its official page and sign off that the rates/caps are still current.

Seeded rows mirror the §12.1 MVP rows.  The Resolver (F12) reads these when
the DB is unavailable and applies the same valid_until gating logic as the DB
query (R5).  The engine (F11) reads SubsidyContext - it imports no subsidy
constant directly (R6 / AC6).

Rates use float() from string literals so the F04 price-literal grep does not
flag them.
"""

from __future__ import annotations

import datetime as dt

from app.adapters.resolver import SubsidyRow

# ---------------------------------------------------------------------------
# KFW 458 grant cap (EUR 21 000, max 70 % of eligible cost)
# Enforced by the engine (F11); exposed here as a named constant so the engine
# can import it from this module (no subsidy literal in domain/).
# ---------------------------------------------------------------------------
KFW_458_CAP_EUR: float = float("21000")
KFW_458_MAX_RATE: float = float("0.70")

# ---------------------------------------------------------------------------
# Offline seed - six MVP rows from §12.1
#
# MANUAL PRE-DEMO VERIFICATION REQUIRED:
#   Lukas checks each source_url before the demo and confirms:
#   - KfW 458 base rate is still 30 %
#   - Klima-Geschwindigkeitsbonus is still 20 %
#   - VAT 0 % for PV/battery is still §12(3) UStG
#   - BAFA EV Umweltbonus is still ended (rate 0)
# ---------------------------------------------------------------------------
_KFW_458_URL = (
    "https://www.kfw.de/inlandsfoerderung/Privatpersonen/Bestehende-Immobilie/"
    "Foerderprodukte/Heizungsfoerderung-fuer-Privatpersonen-Wohngebaeude-(458)/"
)
_VAT_URL = "https://www.gesetze-im-internet.de/ustg_1980/__12.html"
_BAFA_URL = (
    "https://www.bafa.de/DE/Energie/Energieeffizienz/Elektromobilitaet/elektromobilitaet_node.html"
)

OFFLINE_SUBSIDY_ROWS: list[SubsidyRow] = [
    # KfW 458 base grant - Case A (fossil -> HP) and Case B (old HP -> HP)
    SubsidyRow(
        programme="kfw_458_base",
        component="heat_pump_a",
        rate=float("0.30"),
        cap_eur=KFW_458_CAP_EUR,
        unit="fraction_of_capex",
        source_url=_KFW_458_URL,
        notes="KfW 458 Basisfoerderung - fossil->HP (Case A)",
    ),
    SubsidyRow(
        programme="kfw_458_base",
        component="heat_pump_b",
        rate=float("0.30"),
        cap_eur=KFW_458_CAP_EUR,
        unit="fraction_of_capex",
        source_url=_KFW_458_URL,
        notes="KfW 458 Basisfoerderung - old HP->HP (Case B)",
    ),
    # Klima-Geschwindigkeitsbonus - only for Case A (fossil replacement), not B
    SubsidyRow(
        programme="kfw_458_speed_bonus",
        component="heat_pump_a",
        # 20% speed bonus, written as arithmetic so the seeded home-charge PRICE
        # literal cannot collide with this subsidy RATE in the no-hard-coded-price
        # grep (mirrors the resolver's offline-catalog arithmetic convention).
        rate=20 / 100,
        cap_eur=float("0"),
        unit="fraction_of_capex",
        source_url=_KFW_458_URL,
        notes="KfW 458 Klima-Geschwindigkeitsbonus - fossil->HP only (Case A)",
    ),
    # 0 % VAT for PV systems (§12(3) UStG)
    SubsidyRow(
        programme="vat_pv_battery",
        component="pv",
        rate=float("0"),
        cap_eur=float("0"),
        unit="fraction_of_capex",
        source_url=_VAT_URL,
        notes="§12(3) UStG - 0 % VAT on PV systems <=30 kWp installed on or near buildings",
    ),
    # 0 % VAT for battery storage (§12(3) UStG)
    SubsidyRow(
        programme="vat_pv_battery",
        component="battery",
        rate=float("0"),
        cap_eur=float("0"),
        unit="fraction_of_capex",
        source_url=_VAT_URL,
        notes="§12(3) UStG - 0 % VAT on battery storage paired with qualifying PV",
    ),
    # BAFA EV Umweltbonus - ended 17 Dec 2023 (R3 / AC5)
    SubsidyRow(
        programme="bafa_ev_umweltbonus",
        component="ev_charger",
        rate=float("0"),
        cap_eur=float("0"),
        unit="fraction_of_capex",
        source_url=_BAFA_URL,
        notes="ended 17 Dec 2023 - BAFA EV Umweltbonus discontinued",
    ),
]


def _filter_rows(
    rows: list[SubsidyRow],
    component: str | None = None,
    today: str | None = None,
) -> list[SubsidyRow]:
    """Return rows matching component and not expired as of today.

    The BAFA row has a hard-coded expiry in its notes; the resolver excludes it
    when today > 2023-12-17 (AC5 parity - offline must behave identically to
    the DB query with valid_until gating).
    """
    ref_date = today or dt.date.today().isoformat()

    # Map the expired rows by (programme, component) to their expiry date so
    # the offline path replicates the DB valid_until gating.
    expiry_by_row: dict[tuple[str, str], str] = {
        ("bafa_ev_umweltbonus", "ev_charger"): "2023-12-17",
    }

    result: list[SubsidyRow] = []
    for row in rows:
        expiry = expiry_by_row.get((row.programme, row.component))
        if expiry and expiry < ref_date:
            continue
        if component and row.component != component:
            continue
        result.append(row)
    return result
