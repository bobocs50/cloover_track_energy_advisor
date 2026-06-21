"""Pure intake normalisation and baseline reconstruction (F05)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.constants import (
    DEFAULT_OLD_HEATPUMP_SCOP,
    DIESEL_CONSUMPTION_L_PER_100KM,
    EV_CONSUMPTION_KWH_PER_100KM,
    PETROL_CONSUMPTION_L_PER_100KM,
)
from app.domain.models import (
    Address,
    Assumption,
    CarType,
    FuelType,
    Household,
    PricingContext,
)


@dataclass(frozen=True, slots=True)
class ExistingEquipmentState:
    """Owned equipment carried into the engine's starting state."""

    pv_kwp: float
    battery_kwh: float
    heatpump_year: int | None
    heatpump_power_kw: float | None
    heatpump_scop: float | None
    ev: bool
    ev_charger: bool
    pv_incremental_only: bool
    battery_incremental_only: bool
    heatpump_incremental_only: bool
    ev_charger_incremental_only: bool


@dataclass(frozen=True, slots=True)
class NormalisedHousehold:
    """Canonical physical baseline consumed by F06–F11."""

    address: Address
    plz: str
    floor_area_m2: int
    building_year: int
    occupants: int
    heating_fuel: FuelType
    electricity_eur_month: float
    heating_eur_month: float
    mobility_eur_month: float
    mobility_kind: CarType
    annual_consumption_kwh: float
    km_year: float
    mobility_fuel_litres_year: float | None
    mobility_electricity_kwh_year: float | None
    current_monthly_spend_eur: float
    existing: ExistingEquipmentState
    assumptions: tuple[Assumption, ...]


def _assumption(
    field: str,
    value: str,
    source: str,
    *,
    editable: bool,
) -> Assumption:
    return Assumption(field=field, value=value, source=source, editable=editable)


def _require_positive(value: float, field: str) -> None:
    if value <= 0:
        raise ValueError(f"{field} must be greater than zero")


def _require_non_negative(value: float, field: str) -> None:
    if value < 0:
        raise ValueError(f"{field} must not be negative")


def _append_mobility_energy_assumption(
    assumptions: list[Assumption],
    *,
    litres_year: float | None,
    energy_kwh: float | None,
) -> None:
    if litres_year is not None:
        assumptions.append(
            _assumption(
                "mobility_fuel_litres_year",
                f"{litres_year:.2f} litres/year",
                "derived from canonical annual mileage or fuel spend",
                editable=False,
            )
        )
    if energy_kwh is not None:
        assumptions.append(
            _assumption(
                "mobility_electricity_kwh_year",
                f"{energy_kwh:.2f} kWh/year",
                "derived using F03 EV consumption default",
                editable=False,
            )
        )


def _normalise_mobility(
    household: Household,
    context: PricingContext,
    assumptions: list[Assumption],
) -> tuple[CarType, float, float, float | None, float | None]:
    mobility = household.mobility
    kind = CarType.EV if household.existing_ev else mobility.kind

    if kind == CarType.NONE:
        assumptions.append(
            _assumption(
                "km_year",
                "0 km/year",
                "user selected mobility kind NONE",
                editable=False,
            )
        )
        return kind, 0.0, 0.0, None, None

    if mobility.km_month is not None:
        _require_non_negative(mobility.km_month, "mobility.km_month")
        km_year = mobility.km_month * 12
        assumptions.append(
            _assumption(
                "km_year",
                f"{km_year:g} km/year",
                "user: mobility.km_month × 12",
                editable=True,
            )
        )

        if kind == CarType.PETROL:
            litres_year = km_year / 100 * PETROL_CONSUMPTION_L_PER_100KM
            reconstructed_spend = litres_year * context.petrol_per_litre_eur / 12
            energy_kwh = None
        elif kind == CarType.DIESEL:
            litres_year = km_year / 100 * DIESEL_CONSUMPTION_L_PER_100KM
            reconstructed_spend = litres_year * context.diesel_per_litre_eur / 12
            energy_kwh = None
        else:
            litres_year = None
            energy_kwh = km_year / 100 * EV_CONSUMPTION_KWH_PER_100KM
            charging_price = (
                context.home_charge_price_eur_kwh
                if household.existing_ev_charger
                else context.public_charge_per_kwh_eur
            )
            reconstructed_spend = energy_kwh * charging_price / 12

        if mobility.eur_month is not None:
            _require_non_negative(mobility.eur_month, "mobility.eur_month")
            mobility_spend = mobility.eur_month
            spend_source = "user: mobility.eur_month"
        else:
            mobility_spend = reconstructed_spend
            spend_source = "derived from user km and injected unit price"

        assumptions.append(
            _assumption(
                "mobility_eur_month",
                f"{mobility_spend:.2f} EUR/month",
                spend_source,
                editable=mobility.eur_month is not None,
            )
        )
        _append_mobility_energy_assumption(
            assumptions,
            litres_year=litres_year,
            energy_kwh=energy_kwh,
        )
        return kind, km_year, mobility_spend, litres_year, energy_kwh

    if mobility.eur_month is None:
        raise ValueError("mobility requires km_month or eur_month unless kind is NONE")

    _require_non_negative(mobility.eur_month, "mobility.eur_month")
    annual_spend = mobility.eur_month * 12

    if kind == CarType.PETROL:
        litres_year = annual_spend / context.petrol_per_litre_eur
        km_year = litres_year / PETROL_CONSUMPTION_L_PER_100KM * 100
        energy_kwh = None
        derivation = "fuel spend ÷ petrol price ÷ 7.0 L/100 km"
    elif kind == CarType.DIESEL:
        litres_year = annual_spend / context.diesel_per_litre_eur
        km_year = litres_year / DIESEL_CONSUMPTION_L_PER_100KM * 100
        energy_kwh = None
        derivation = "fuel spend ÷ diesel price ÷ 6.0 L/100 km"
    else:
        litres_year = None
        energy_kwh = annual_spend / context.public_charge_per_kwh_eur
        km_year = energy_kwh / EV_CONSUMPTION_KWH_PER_100KM * 100
        derivation = "charging spend ÷ public-charge price ÷ 18 kWh/100 km"

    assumptions.append(
        _assumption(
            "km_year",
            f"{km_year:.2f} km/year",
            f"derived: {derivation}",
            editable=True,
        )
    )
    assumptions.append(
        _assumption(
            "mobility_eur_month",
            f"{mobility.eur_month:.2f} EUR/month",
            "user: mobility.eur_month",
            editable=True,
        )
    )
    _append_mobility_energy_assumption(
        assumptions,
        litres_year=litres_year,
        energy_kwh=energy_kwh,
    )
    return kind, km_year, mobility.eur_month, litres_year, energy_kwh


def normalise_household(
    household: Household,
    context: PricingContext,
) -> NormalisedHousehold:
    """Convert a validated Household into the deterministic physical baseline."""
    _require_positive(context.retail_price_eur_kwh, "retail_price_eur_kwh")
    _require_positive(context.petrol_per_litre_eur, "petrol_per_litre_eur")
    _require_positive(context.diesel_per_litre_eur, "diesel_per_litre_eur")
    _require_positive(context.public_charge_per_kwh_eur, "public_charge_per_kwh_eur")
    _require_positive(context.home_charge_price_eur_kwh, "home_charge_price_eur_kwh")
    _require_non_negative(household.electricity_eur_month, "electricity_eur_month")
    _require_non_negative(household.heating.eur_month, "heating.eur_month")

    assumptions = [
        _assumption(
            "retail_price_eur_kwh",
            f"{context.retail_price_eur_kwh:g} EUR/kWh",
            "price_catalog: retail_per_kwh",
            editable=False,
        ),
        _assumption(
            "petrol_per_litre_eur",
            f"{context.petrol_per_litre_eur:g} EUR/litre",
            "price_catalog: petrol_per_litre",
            editable=False,
        ),
        _assumption(
            "diesel_per_litre_eur",
            f"{context.diesel_per_litre_eur:g} EUR/litre",
            "price_catalog: diesel_per_litre",
            editable=False,
        ),
        _assumption(
            "public_charge_per_kwh_eur",
            f"{context.public_charge_per_kwh_eur:g} EUR/kWh",
            "price_catalog: public_charge_per_kwh",
            editable=False,
        ),
        _assumption(
            "petrol_consumption_l_per_100km",
            f"{PETROL_CONSUMPTION_L_PER_100KM:g} L/100 km",
            "F03 physics default; ADAC class reference",
            editable=True,
        ),
        _assumption(
            "diesel_consumption_l_per_100km",
            f"{DIESEL_CONSUMPTION_L_PER_100KM:g} L/100 km",
            "F03 physics default; ADAC class reference",
            editable=True,
        ),
        _assumption(
            "ev_consumption_kwh_per_100km",
            f"{EV_CONSUMPTION_KWH_PER_100KM:g} kWh/100 km",
            "F03 physics class default",
            editable=True,
        ),
    ]

    annual_consumption_kwh = household.electricity_eur_month * 12 / context.retail_price_eur_kwh
    assumptions.append(
        _assumption(
            "annual_consumption_kwh",
            f"{annual_consumption_kwh:.2f} kWh/year",
            "derived: electricity_eur_month × 12 ÷ retail price",
            editable=False,
        )
    )

    kind, km_year, mobility_spend, litres_year, mobility_kwh = _normalise_mobility(
        household,
        context,
        assumptions,
    )

    if household.existing_heatpump_power_kw is None:
        assumptions.append(
            _assumption(
                "existing_heatpump_power_kw",
                "area-method fallback",
                "F03/F08: floor area × building-year heat-load factor",
                editable=True,
            )
        )
    else:
        assumptions.append(
            _assumption(
                "existing_heatpump_power_kw",
                f"{household.existing_heatpump_power_kw:g} kW",
                "user",
                editable=True,
            )
        )

    if household.existing_heatpump_scop is None:
        assumptions.append(
            _assumption(
                "existing_heatpump_scop",
                f"{DEFAULT_OLD_HEATPUMP_SCOP:g}",
                "F03/F08 age-regression fallback",
                editable=True,
            )
        )
    else:
        assumptions.append(
            _assumption(
                "existing_heatpump_scop",
                f"{household.existing_heatpump_scop:g}",
                "user",
                editable=True,
            )
        )

    has_existing_heatpump = any(
        value is not None
        for value in (
            household.existing_heatpump_year,
            household.existing_heatpump_power_kw,
            household.existing_heatpump_scop,
        )
    )
    existing = ExistingEquipmentState(
        pv_kwp=household.existing_pv_kwp,
        battery_kwh=household.existing_battery_kwh,
        heatpump_year=household.existing_heatpump_year,
        heatpump_power_kw=household.existing_heatpump_power_kw,
        heatpump_scop=household.existing_heatpump_scop,
        ev=household.existing_ev,
        ev_charger=household.existing_ev_charger,
        pv_incremental_only=household.existing_pv_kwp > 0,
        battery_incremental_only=household.existing_battery_kwh > 0,
        heatpump_incremental_only=has_existing_heatpump,
        ev_charger_incremental_only=(household.existing_ev and not household.existing_ev_charger),
    )
    assumptions.append(
        _assumption(
            "existing_equipment_accounting",
            "capex and saving credit apply to incremental delta only",
            "F03 §1 / F05 §3.2",
            editable=False,
        )
    )

    current_monthly_spend = (
        household.electricity_eur_month + household.heating.eur_month + mobility_spend
    )

    return NormalisedHousehold(
        address=household.address,
        plz=household.plz,
        floor_area_m2=household.floor_area_m2,
        building_year=household.building_year,
        occupants=household.occupants,
        heating_fuel=household.heating.fuel,
        electricity_eur_month=household.electricity_eur_month,
        heating_eur_month=household.heating.eur_month,
        mobility_eur_month=mobility_spend,
        mobility_kind=kind,
        annual_consumption_kwh=annual_consumption_kwh,
        km_year=km_year,
        mobility_fuel_litres_year=litres_year,
        mobility_electricity_kwh_year=mobility_kwh,
        current_monthly_spend_eur=current_monthly_spend,
        existing=existing,
        assumptions=tuple(assumptions),
    )