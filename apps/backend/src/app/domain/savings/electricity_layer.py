"""Electricity savings via the unified state-cost model (F06, F07).

Owner: Lukas (engine)
Feature ID: F06 (layer1 solar) / F07 (layer2 battery)

DD-1 decision: a single PV credit covers the total electricity meter
(base load + heat-pump load).  EV charging is priced separately (no PV
share).  Both layers are implicit in state_annual_elec_cost(); the
marginal ladder is built in scenarios.py by diffing states.
"""

from __future__ import annotations

from app.domain.constants import (
    AUTARKY_PV_ONLY,
    AUTARKY_WITH_BATTERY,
    BATTERY_CYCLES_PER_YEAR,
    BATTERY_ROUND_TRIP_EFFICIENCY,
)


def battery_arbitrage_value(
    *,
    battery_kwh: float,
    dynamic_spread_eur_kwh: float,
) -> float:
    """Annual EUR value from battery buy-low/sell-high dynamic tariff arbitrage (spec §5.2).

    Assumes full cycles_per_year × round_trip efficiency utilisation.
    The arbitrage capacity is treated as distinct from the self-consumption
    shift already captured by the autarky factor change.
    """
    return (
        battery_kwh
        * BATTERY_CYCLES_PER_YEAR
        * BATTERY_ROUND_TRIP_EFFICIENCY
        * dynamic_spread_eur_kwh
    )


def state_annual_elec_cost(
    *,
    total_demand_kwh: float,
    pv_kwp: float,
    has_battery: bool,
    specific_yield_kwh_per_kwp: float,
    retail_price_eur_kwh: float,
    feedin_price_eur_kwh: float,
) -> float:
    """Annual EUR electricity cost for a given meter state (lower = better).

    Parameters
    ----------
    total_demand_kwh:
        Combined annual electricity demand (base + heat-pump load; EV
        excluded per DD-1).
    pv_kwp:
        Total installed PV capacity in kWp (existing + added).
    has_battery:
        True when a battery is present in this state.
    specific_yield_kwh_per_kwp:
        Site-specific annual yield per kWp (from PVGIS / fallback).
    retail_price_eur_kwh:
        Grid import price in EUR/kWh.
    feedin_price_eur_kwh:
        Feed-in tariff in EUR/kWh.

    Returns
    -------
    float
        Annual electricity cost in EUR.  May be negative if feed-in
        revenue exceeds import cost (large PV + low demand).
    """
    pv_yield = pv_kwp * specific_yield_kwh_per_kwp

    if pv_kwp <= 0.0:
        # No PV — pay full retail for all demand
        return total_demand_kwh * retail_price_eur_kwh

    autarky = AUTARKY_WITH_BATTERY if has_battery else AUTARKY_PV_ONLY
    self_consumed = min(autarky * total_demand_kwh, pv_yield)
    exported = max(0.0, pv_yield - self_consumed)
    grid_import = total_demand_kwh - self_consumed

    return grid_import * retail_price_eur_kwh - exported * feedin_price_eur_kwh