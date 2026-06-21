"""Mobility layer — EV home charging replaces petrol/diesel/public charging (F09).

Owner: Lukas (engine)
Feature ID: F09 (layer4 EV charger)

DD-1: EV charging is priced at the injected home_charge_price_eur_kwh
(off-peak/grid blend) with no free-PV share.  EV demand is excluded from
the PV meter (state_annual_elec_cost).

Three sub-cases:
- NONE:          no car → no offer, no mobility cost.
- Case A (fossil car): current spend = fuel cost; new cost = home charging.
- Case B (EV already, no charger): current spend = public charging;
  new cost = home charging.
- existing_ev_charger=True: no offer (rung skipped).
"""

from __future__ import annotations

from app.domain.constants import EV_CONSUMPTION_KWH_PER_100KM
from app.domain.models import CarType


def ev_kwh_year(km_year: float) -> float:
    """Annual EV electricity demand for a given mileage."""
    return km_year * EV_CONSUMPTION_KWH_PER_100KM / 100.0


def baseline_mobility_cost_year(
    *,
    km_year: float,
    mobility_kind: CarType,
    mobility_eur_month: float,
    public_charge_per_kwh_eur: float,
    home_charge_price_eur_kwh: float,
    existing_ev_charger: bool,
) -> float:
    """Annual baseline mobility cost in EUR.

    For fossil cars the user-supplied spend is the authority.
    For existing-EV without a charger the baseline is public-charging cost.
    """
    if mobility_kind == CarType.NONE:
        return 0.0
    if mobility_kind == CarType.EV:
        kwh_year = ev_kwh_year(km_year)
        if existing_ev_charger:
            # Already has charger; home charging is the baseline
            return kwh_year * home_charge_price_eur_kwh
        # Case B: public charging is today's spend
        return kwh_year * public_charge_per_kwh_eur
    # Fossil car: user-supplied monthly spend is canonical (spec §4, §5.4)
    return mobility_eur_month * 12.0


def new_mobility_cost_year(
    *,
    km_year: float,
    home_charge_price_eur_kwh: float,
) -> float:
    """Annual home-charging cost in EUR for the new state (EV charger installed)."""
    return ev_kwh_year(km_year) * home_charge_price_eur_kwh