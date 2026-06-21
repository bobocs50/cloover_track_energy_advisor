"""Heating layer — heat pump replaces fossil or old-HP baseline (F08).

Owner: Lukas (engine)
Feature ID: F08 (layer3 heat pump)

Two cases per spec §5.3 and DD-1:
- Case A: fossil fuel (oil or gas) → new heat pump (SCOP 3.5)
- Case B: old heat pump → modern heat pump (SCOP 4.0)

Heat-pump electricity demand is returned so the electricity meter
(state_annual_elec_cost in electricity.py) can fold it in for L3+ states.
No second PV-overlap discount is applied here (DD-1).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.constants import (
    DEFAULT_OLD_HEATPUMP_SCOP,
    GAS_BOILER_EFFICIENCY,
    NEW_HEATPUMP_SCOP_FOSSIL,
    NEW_HEATPUMP_SCOP_OLDHP,
    OIL_BOILER_EFFICIENCY,
    OIL_KWH_PER_LITRE,
)
from app.domain.models import FuelType


@dataclass(frozen=True, slots=True)
class HeatingBaseline:
    """Derived heating quantities consumed by the ladder."""

    # True when the household already has a heat pump
    is_old_hp: bool
    # Annual heat demand in kWh (fossil input or old-HP thermal output)
    heat_demand_kwh: float
    # Electricity the NEW heat pump needs annually (folded into elec meter for L3+)
    new_hp_elec_kwh: float
    # Electricity the OLD heat pump uses today (folded into elec meter even for L1/L2
    # states when is_old_hp is True; the baseline state already includes it)
    old_hp_elec_kwh: float
    # Old SCOP used in Case B (informational)
    old_scop: float


def compute_heating_baseline(
    *,
    heating_fuel: FuelType,
    heating_eur_month: float,
    oil_per_litre_eur: float,
    gas_per_kwh_eur: float,
    retail_price_eur_kwh: float,
    existing_heatpump_scop: float | None,
    is_old_hp: bool,
) -> HeatingBaseline:
    """Derive all heating quantities needed by the ladder.

    Parameters
    ----------
    heating_fuel:
        Fuel type from the Household (OIL or GAS); ignored for Case B.
    heating_eur_month:
        Current monthly heating spend in EUR.
    oil_per_litre_eur, gas_per_kwh_eur, retail_price_eur_kwh:
        Injected prices.
    existing_heatpump_scop:
        Measured or nameplate SCOP of the existing HP; None → default.
    is_old_hp:
        True for Case B (existing HP present and eligible for upgrade).
    """
    annual_heating_spend = heating_eur_month * 12

    if is_old_hp:
        # Case B: old HP → modern HP
        old_scop = (
            existing_heatpump_scop
            if existing_heatpump_scop is not None
            else DEFAULT_OLD_HEATPUMP_SCOP
        )
        # Infer heat demand from current electricity bill (at old SCOP)
        old_hp_elec_kwh = annual_heating_spend / retail_price_eur_kwh
        heat_demand_kwh = old_hp_elec_kwh * old_scop
        new_hp_elec_kwh = heat_demand_kwh / NEW_HEATPUMP_SCOP_OLDHP
        return HeatingBaseline(
            is_old_hp=True,
            heat_demand_kwh=heat_demand_kwh,
            new_hp_elec_kwh=new_hp_elec_kwh,
            old_hp_elec_kwh=old_hp_elec_kwh,
            old_scop=old_scop,
        )

    # Case A: fossil → new HP
    if heating_fuel == FuelType.OIL:
        heat_demand_kwh = (
            annual_heating_spend / oil_per_litre_eur * OIL_KWH_PER_LITRE * OIL_BOILER_EFFICIENCY
        )
    else:
        # GAS
        heat_demand_kwh = annual_heating_spend / gas_per_kwh_eur * GAS_BOILER_EFFICIENCY

    new_hp_elec_kwh = heat_demand_kwh / NEW_HEATPUMP_SCOP_FOSSIL

    return HeatingBaseline(
        is_old_hp=False,
        heat_demand_kwh=heat_demand_kwh,
        new_hp_elec_kwh=new_hp_elec_kwh,
        old_hp_elec_kwh=0.0,
        old_scop=0.0,
    )