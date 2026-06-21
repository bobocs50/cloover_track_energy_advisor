"""Cumulative scenario ladder — 4 rungs (F10).

Owner: Lukas (engine)
Feature ID: F10 (optimiser / configurator ladder)

The four layers are CUMULATIVE and COUPLED through one electricity meter
(DD-1).  Each rung is a STATE; gross savings are derived by diffing total
annual costs.  Marginal deltas are taken over consecutive states so that
Σ delta_net == headline exactly (no residual).

Rungs: solar → +battery → +heat pump → +EV charger.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.constants import (
    BATTERY_CYCLES_PER_YEAR,
    BATTERY_MAX_KWH,
    BATTERY_MIN_KWH,
    BATTERY_ROUND_TRIP_EFFICIENCY,
    HP_OFFER_AGE_THRESHOLD_YEARS,
    KFW_FOSSIL,
    KFW_OLDHP,
)
from app.domain.models import (
    Breakdown,
    Capex,
    Confidence,
    PricingContext,
    ScenarioResult,
)
from app.domain.savings.electricity_layer import battery_arbitrage_value, state_annual_elec_cost
from app.domain.savings.financing import annuity
from app.domain.savings.heatpump_layer import HeatingBaseline, compute_heating_baseline
from app.domain.savings.intake import NormalisedHousehold
from app.domain.savings.ev_layer import (
    baseline_mobility_cost_year,
    ev_kwh_year,
    new_mobility_cost_year,
)
from app.domain.savings.subsidy_layer.catalog import SubsidyContext


def _resolve_hp_rate(subsidies: SubsidyContext | None, *, is_old_hp: bool) -> float:
    """KfW heat-pump grant rate, sourced from the subsidy catalog when wired (Layer 5).

    Case A (fossil → HP) maps to catalog component ``heat_pump_a`` (base 30% +
    Klima-Geschwindigkeitsbonus 20% = 50%); Case B (old HP → new HP) maps to
    ``heat_pump_b`` (base 30% only).  With no SubsidyContext injected the engine
    falls back to the frozen constants so the F03 worked example still holds.
    """
    if subsidies is not None:
        return subsidies.combined_rate("heat_pump_b" if is_old_hp else "heat_pump_a")
    return KFW_OLDHP if is_old_hp else KFW_FOSSIL

# ---------------------------------------------------------------------------
# Sizing heuristic
# ---------------------------------------------------------------------------


def _ceil_to_half(x: float) -> float:
    """Round up to the nearest 0.5 kWp."""
    return math.ceil(x * 2.0) / 2.0


def recommend_pv_kwp(
    *,
    annual_consumption_kwh: float,
    hp_elec_kwh: float,
    km_year: float,
    existing_pv_kwp: float,
    specific_yield: float,
) -> float:
    """Deterministic PV sizing: cover ~80% of total electric demand.

    The 0.80 fraction targets ~80% annual yield coverage of the combined
    load (base + heat-pump + EV).  For the V_WORKED_BASE case this produces
    ceil₀.₅(10514 × 0.80 / 980) = ceil₀.₅(8.583) = 9.0 kWp exactly,
    matching the spec's worked example.  The result is clamped so it never
    falls below existing capacity.
    """
    total_demand = annual_consumption_kwh + hp_elec_kwh + ev_kwh_year(km_year)
    raw_kwp = total_demand * 0.80 / specific_yield
    return max(existing_pv_kwp, _ceil_to_half(raw_kwp))


def recommend_battery_kwh(
    *,
    annual_consumption_kwh: float,
    hp_elec_kwh: float,
    existing_battery_kwh: float,
) -> float:
    """Deterministic battery sizing: 1 kWh per 1 MWh meter demand, clamped 5..10.

    Meter demand = base load + heat-pump load (EV is excluded per DD-1).
    For the V_WORKED_BASE case: round((3081 + 4769) / 1000) = round(7.85) = 8 kWh.
    """
    meter_demand = annual_consumption_kwh + hp_elec_kwh
    raw = round(meter_demand / 1000.0)
    clamped = max(BATTERY_MIN_KWH, min(BATTERY_MAX_KWH, raw))
    return max(existing_battery_kwh, clamped)


# ---------------------------------------------------------------------------
# State cost model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _EngineState:
    """Snapshot of installed equipment at one rung."""

    pv_kwp: float
    battery_kwh: float
    heat_pump: bool
    ev_charger: bool


def _state_annual_costs(
    state: _EngineState,
    *,
    base_demand_kwh: float,
    heating_baseline: HeatingBaseline,
    heating_eur_month: float,
    km_year: float,
    mobility_kind: str,
    mobility_eur_month: float,
    public_charge_per_kwh_eur: float,
    home_charge_price_eur_kwh: float,
    existing_ev_charger_in_baseline: bool,
    specific_yield: float,
    retail_price_eur_kwh: float,
    feedin_price_eur_kwh: float,
    dynamic_spread_eur_kwh: float,
) -> tuple[float, float, float]:
    """Return (elec_cost, heating_cost, mobility_cost) for a given state.

    Electricity meter folds in heat-pump load (DD-1).
    Battery arbitrage is added as a negative cost (revenue) per spec §5.2.
    EV charging is priced separately at home_charge_price (DD-1, no PV share).
    """
    # Electricity demand for the meter
    hp_load = (
        heating_baseline.new_hp_elec_kwh
        if state.heat_pump
        else (heating_baseline.old_hp_elec_kwh if heating_baseline.is_old_hp else 0.0)
    )
    meter_demand = base_demand_kwh + hp_load

    elec_cost = state_annual_elec_cost(
        total_demand_kwh=meter_demand,
        pv_kwp=state.pv_kwp,
        has_battery=state.battery_kwh > 0.0,
        specific_yield_kwh_per_kwp=specific_yield,
        retail_price_eur_kwh=retail_price_eur_kwh,
        feedin_price_eur_kwh=feedin_price_eur_kwh,
    )

    # Battery arbitrage revenue (spec §5.2): buy cheap / sell dear on dynamic tariff.
    # This is additive over the self-consumption saving captured by the autarky shift.
    if state.battery_kwh > 0.0:
        elec_cost -= battery_arbitrage_value(
            battery_kwh=state.battery_kwh,
            dynamic_spread_eur_kwh=dynamic_spread_eur_kwh,
        )

    # Heating cost: fossil spend unless HP is in this state (or old HP → already zero)
    if state.heat_pump or heating_baseline.is_old_hp:
        heating_cost = 0.0
    else:
        heating_cost = heating_eur_month * 12.0

    # Mobility cost (EV charging is outside the PV meter)
    from app.domain.models import CarType  # local import avoids circular

    if mobility_kind == CarType.NONE:
        mobility_cost = 0.0
    elif state.ev_charger:
        mobility_cost = new_mobility_cost_year(
            km_year=km_year,
            home_charge_price_eur_kwh=home_charge_price_eur_kwh,
        )
    elif mobility_kind == CarType.EV:
        # Existing EV without a charger: paying public-charge rates
        mobility_cost = ev_kwh_year(km_year) * public_charge_per_kwh_eur
    else:
        # Fossil car pre-EV
        mobility_cost = mobility_eur_month * 12.0

    return elec_cost, heating_cost, mobility_cost


# ---------------------------------------------------------------------------
# Capex helpers
# ---------------------------------------------------------------------------


def _capex_solar(
    *,
    rec_pv_kwp: float,
    existing_pv_kwp: float,
    pv_per_kwp_eur: float,
) -> tuple[float, float, float, str]:
    """Return (gross, subsidy, after_subsidy, note) for the solar layer."""
    added = max(0.0, rec_pv_kwp - existing_pv_kwp)
    gross = added * pv_per_kwp_eur
    # PV/battery: 0% VAT (net prices already) → subsidy = 0
    return gross, 0.0, gross, f"{added:.1f} kWp × €{pv_per_kwp_eur:,.0f}/kWp; 0% VAT"


def _capex_battery(
    *,
    rec_batt_kwh: float,
    existing_batt_kwh: float,
    battery_per_kwh_eur: float,
) -> tuple[float, float, float, str]:
    """Return (gross, subsidy, after_subsidy, note) for the battery layer."""
    added = max(0.0, rec_batt_kwh - existing_batt_kwh)
    gross = added * battery_per_kwh_eur
    return gross, 0.0, gross, f"{added:.1f} kWh × €{battery_per_kwh_eur:,.0f}/kWh; 0% VAT"


def _capex_heatpump(
    *,
    heatpump_fixed_eur: float,
    hp_rate: float,
) -> tuple[float, float, float, str]:
    """Return (gross, subsidy, after_subsidy, note) for the heat-pump layer.

    ``hp_rate`` is resolved upstream from the subsidy catalog (Layer 5) or the
    frozen constants — see :func:`_resolve_hp_rate`.
    """
    subsidy = heatpump_fixed_eur * hp_rate
    after = heatpump_fixed_eur - subsidy
    return (
        heatpump_fixed_eur,
        subsidy,
        after,
        f"€{heatpump_fixed_eur:,.0f} HP − KfW 458 {hp_rate * 100:.0f}% = €{after:,.0f}",
    )


def _capex_ev(*, wallbox_fixed_eur: float) -> tuple[float, float, float, str]:
    """Return (gross, subsidy, after_subsidy, note) for the EV charger layer."""
    return (
        wallbox_fixed_eur,
        0.0,
        wallbox_fixed_eur,
        f"€{wallbox_fixed_eur:,.0f} wallbox; 0% subsidy",
    )


# ---------------------------------------------------------------------------
# Break-even simulation
# ---------------------------------------------------------------------------


def _break_even_month(
    *,
    monthly_saving_eur: float,
    saving_after_payoff_eur: float,
    term_months: int,
) -> int:
    """Simulate cumulative cash flow; return first month where balance >= 0."""
    if monthly_saving_eur >= 0.0:
        return 1
    balance = 0.0
    cap = term_months + 600
    for month in range(1, cap + 1):
        balance += monthly_saving_eur if month <= term_months else saving_after_payoff_eur
        if balance >= 0.0:
            return month
    return cap


# ---------------------------------------------------------------------------
# Confidence band
# ---------------------------------------------------------------------------


def _compute_confidence(
    *,
    base_headline: float,
    nh: NormalisedHousehold,
    ctx: PricingContext,
    specific_yield: float,
    rec_pv_kwp: float,
    rec_batt_kwh: float,
    offer_hp: bool,
    offer_ev: bool,
    heating_baseline: HeatingBaseline,
    hp_rate: float,
) -> Confidence:
    """Evaluate low/high perturbations and return the confidence band.

    Drivers tested (spec §7):
    - irradiance: specific_yield ±8%
    - dynamic_spread: ctx.dynamic_spread × {0.5, 2.0}
    - hp_subsidy: rate over {0.30, 0.70} (only if HP offered)
    - autarky: autarky factors ±0.10

    biggest_driver = driver with the largest (high − low) span.
    """
    from app.domain.constants import (
        AUTARKY_PV_ONLY as A_PV,
    )
    from app.domain.constants import (
        AUTARKY_WITH_BATTERY as A_BATT,
    )

    def _headline(
        sy: float,
        spread_mult: float,
        hp_subsidy_rate: float | None,
        autarky_delta: float,
    ) -> float:
        ctx2 = ctx.model_copy(
            update={"dynamic_spread_eur_kwh": ctx.dynamic_spread_eur_kwh * spread_mult}
        )
        hb2 = heating_baseline

        # Recompute the electricity cost inline with adjusted autarky factors.
        a_pv = max(0.0, min(1.0, A_PV + autarky_delta))
        a_batt = max(0.0, min(1.0, A_BATT + autarky_delta))

        def _elec_cost_perturbed(
            demand: float, pv: float, has_batt: bool, batt_kwh: float
        ) -> float:
            pv_yield = pv * sy
            if pv <= 0.0:
                base_cost = demand * ctx2.retail_price_eur_kwh
            else:
                aut = a_batt if has_batt else a_pv
                sc = min(aut * demand, pv_yield)
                exp_ = max(0.0, pv_yield - sc)
                base_cost = (
                    demand - sc
                ) * ctx2.retail_price_eur_kwh - exp_ * ctx2.feedin_price_eur_kwh
            # Subtract battery arbitrage revenue
            if batt_kwh > 0.0:
                base_cost -= (
                    batt_kwh
                    * BATTERY_CYCLES_PER_YEAR
                    * BATTERY_ROUND_TRIP_EFFICIENCY
                    * ctx2.dynamic_spread_eur_kwh
                )
            return base_cost

        # Baseline cost
        s0_meter = nh.annual_consumption_kwh + (hb2.old_hp_elec_kwh if hb2.is_old_hp else 0.0)
        s0_elec = _elec_cost_perturbed(
            s0_meter,
            nh.existing.pv_kwp,
            nh.existing.battery_kwh > 0.0,
            nh.existing.battery_kwh,
        )
        s0_heat = 0.0 if hb2.is_old_hp else nh.heating_eur_month * 12.0
        s0_mob = baseline_mobility_cost_year(
            km_year=nh.km_year,
            mobility_kind=nh.mobility_kind,
            mobility_eur_month=nh.mobility_eur_month,
            public_charge_per_kwh_eur=ctx2.public_charge_per_kwh_eur,
            home_charge_price_eur_kwh=ctx2.home_charge_price_eur_kwh,
            existing_ev_charger=nh.existing.ev_charger,
        )
        s0_total = s0_elec + s0_heat + s0_mob

        # Last rung (full bundle with HP and EV if offered)
        lp_meter = nh.annual_consumption_kwh + (
            hb2.new_hp_elec_kwh if offer_hp else (hb2.old_hp_elec_kwh if hb2.is_old_hp else 0.0)
        )
        lp_elec = _elec_cost_perturbed(lp_meter, rec_pv_kwp, rec_batt_kwh > 0.0, rec_batt_kwh)
        lp_heat = 0.0
        if offer_ev:
            lp_mob = new_mobility_cost_year(
                km_year=nh.km_year,
                home_charge_price_eur_kwh=ctx2.home_charge_price_eur_kwh,
            )
        else:
            lp_mob = s0_mob

        gross_year = s0_total - (lp_elec + lp_heat + lp_mob)

        # Capex
        solar_gross = max(0.0, rec_pv_kwp - nh.existing.pv_kwp) * ctx2.pv_per_kwp_eur
        batt_gross = max(0.0, rec_batt_kwh - nh.existing.battery_kwh) * ctx2.battery_per_kwh_eur
        hp_gross = ctx2.heatpump_fixed_eur if offer_hp else 0.0
        ev_gross = ctx2.wallbox_fixed_eur if offer_ev else 0.0

        if offer_hp:
            rate = hp_subsidy_rate if hp_subsidy_rate is not None else hp_rate
            hp_net = hp_gross * (1.0 - rate)
        else:
            hp_net = 0.0

        total_net_capex = solar_gross + batt_gross + hp_net + ev_gross
        inst = annuity(total_net_capex, ctx2.financing_apr, ctx2.financing_term_months)
        return gross_year / 12.0 - inst

    # Base headline sanity check (should match base_headline within fp noise)
    h_base = base_headline

    # Driver: irradiance ±8%
    h_irr_low = _headline(specific_yield * 0.92, 1.0, None, 0.0)
    h_irr_high = _headline(specific_yield * 1.08, 1.0, None, 0.0)

    # Driver: dynamic spread ×0.5 / ×2.0
    h_spread_low = _headline(specific_yield, 0.5, None, 0.0)
    h_spread_high = _headline(specific_yield, 2.0, None, 0.0)

    # Driver: HP subsidy 30% / 70% (if HP offered)
    if offer_hp:
        h_hpsub_low = _headline(
            specific_yield, 1.0, 0.70, 0.0
        )  # higher subsidy = lower install = higher net
        h_hpsub_high = _headline(
            specific_yield, 1.0, 0.30, 0.0
        )  # lower subsidy = higher install = lower net
        # Normalise so "high" > "low"
        h_hpsub_lo = min(h_hpsub_low, h_hpsub_high)
        h_hpsub_hi = max(h_hpsub_low, h_hpsub_high)
    else:
        h_hpsub_lo = h_base
        h_hpsub_hi = h_base

    # Driver: autarky ±0.10
    h_aut_low = _headline(specific_yield, 1.0, None, -0.10)
    h_aut_high = _headline(specific_yield, 1.0, None, +0.10)

    drivers = {
        "irradiance": (min(h_irr_low, h_irr_high), max(h_irr_low, h_irr_high)),
        "dynamic_spread": (min(h_spread_low, h_spread_high), max(h_spread_low, h_spread_high)),
        "hp_subsidy": (h_hpsub_lo, h_hpsub_hi),
        "autarky": (min(h_aut_low, h_aut_high), max(h_aut_low, h_aut_high)),
    }

    overall_low = min(v[0] for v in drivers.values())
    overall_high = max(v[1] for v in drivers.values())
    band = (overall_high - overall_low) / 2.0

    biggest_driver = max(drivers, key=lambda d: drivers[d][1] - drivers[d][0])

    return Confidence(
        band_eur=round(band, 2),
        low_eur=round(h_base - band, 2),
        high_eur=round(h_base + band, 2),
        biggest_driver=biggest_driver,
    )


# ---------------------------------------------------------------------------
# Public API: build_ladder
# ---------------------------------------------------------------------------


def build_ladder(
    nh: NormalisedHousehold,
    ctx: PricingContext,
    specific_yield: float,
    subsidies: SubsidyContext | None = None,
) -> list[ScenarioResult]:
    """Build the cumulative savings ladder (2–4 rungs).

    Returns rungs in canonical order: solar → battery → heat pump → EV.
    HP rung is omitted if the household has a modern HP.
    EV rung is omitted if the household already has a charger.

    ``subsidies`` is the Layer 5 catalog context (KfW/BAFA/VAT).  When omitted
    the engine falls back to the frozen KfW constants, so existing test vectors
    are unaffected.
    """
    # --- Heating baseline ---------------------------------------------------
    is_old_hp = _is_old_hp(nh)
    offer_hp = _should_offer_hp(nh)

    # --- Heat-pump grant rate (Layer 5 catalog or constant fallback) --------
    hp_rate = _resolve_hp_rate(subsidies, is_old_hp=is_old_hp)

    heating_baseline = compute_heating_baseline(
        heating_fuel=nh.heating_fuel,
        heating_eur_month=nh.heating_eur_month,
        oil_per_litre_eur=ctx.oil_per_litre_eur,
        gas_per_kwh_eur=ctx.gas_per_kwh_eur,
        retail_price_eur_kwh=ctx.retail_price_eur_kwh,
        existing_heatpump_scop=nh.existing.heatpump_scop,
        is_old_hp=is_old_hp,
    )

    # --- Sizing -------------------------------------------------------------
    rec_pv_kwp = recommend_pv_kwp(
        annual_consumption_kwh=nh.annual_consumption_kwh,
        hp_elec_kwh=heating_baseline.new_hp_elec_kwh
        if offer_hp
        else (heating_baseline.old_hp_elec_kwh if is_old_hp else 0.0),
        km_year=nh.km_year,
        existing_pv_kwp=nh.existing.pv_kwp,
        specific_yield=specific_yield,
    )
    rec_batt_kwh = recommend_battery_kwh(
        annual_consumption_kwh=nh.annual_consumption_kwh,
        hp_elec_kwh=heating_baseline.new_hp_elec_kwh
        if offer_hp
        else (heating_baseline.old_hp_elec_kwh if is_old_hp else 0.0),
        existing_battery_kwh=nh.existing.battery_kwh,
    )

    from app.domain.models import CarType

    offer_ev = nh.mobility_kind != CarType.NONE and not nh.existing.ev_charger

    # --- Baseline state (S0) ------------------------------------------------
    s0 = _EngineState(
        pv_kwp=nh.existing.pv_kwp,
        battery_kwh=nh.existing.battery_kwh,
        heat_pump=False,  # HP is not in baseline (old HP costs tracked separately)
        ev_charger=nh.existing.ev_charger,
    )

    def _cost(state: _EngineState) -> tuple[float, float, float]:
        return _state_annual_costs(
            state,
            base_demand_kwh=nh.annual_consumption_kwh,
            heating_baseline=heating_baseline,
            heating_eur_month=nh.heating_eur_month,
            km_year=nh.km_year,
            mobility_kind=nh.mobility_kind,
            mobility_eur_month=nh.mobility_eur_month,
            public_charge_per_kwh_eur=ctx.public_charge_per_kwh_eur,
            home_charge_price_eur_kwh=ctx.home_charge_price_eur_kwh,
            existing_ev_charger_in_baseline=nh.existing.ev_charger,
            specific_yield=specific_yield,
            retail_price_eur_kwh=ctx.retail_price_eur_kwh,
            feedin_price_eur_kwh=ctx.feedin_price_eur_kwh,
            dynamic_spread_eur_kwh=ctx.dynamic_spread_eur_kwh,
        )

    s0_costs = _cost(s0)
    s0_total = sum(s0_costs)

    # --- Rung states --------------------------------------------------------
    r1 = _EngineState(rec_pv_kwp, nh.existing.battery_kwh, False, nh.existing.ev_charger)
    r2 = _EngineState(rec_pv_kwp, rec_batt_kwh, False, nh.existing.ev_charger)
    r3 = _EngineState(rec_pv_kwp, rec_batt_kwh, True, nh.existing.ev_charger) if offer_hp else None
    r4 = (
        _EngineState(
            rec_pv_kwp,
            rec_batt_kwh,
            offer_hp,  # HP is in state if offered
            True,
        )
        if offer_ev
        else None
    )

    # --- Per-layer delta_gross (annual, split by bucket) --------------------
    # Gross saving = cost(prev) - cost(rung).  Bucket attribution:
    #   solar, battery → electricity bucket
    #   heatpump → heating bucket
    #   ev → mobility bucket
    prev_state = s0
    prev_total = s0_total

    # Cumulative capex trackers
    cum_capex_gross = 0.0
    cum_capex_subsidy = 0.0
    cum_capex_after = 0.0
    cum_installment = 0.0

    # Cumulative bucket savings (annual)
    cum_elec_gross_year = 0.0
    cum_heat_gross_year = 0.0
    cum_mob_gross_year = 0.0

    results: list[ScenarioResult] = []

    def _make_rung(
        label_str: str,
        scenario_id: str,
        state: _EngineState,
        layer_bucket: str,  # "electricity" | "heating" | "mobility"
        layer_capex: tuple[float, float, float, str],
    ) -> ScenarioResult:
        nonlocal prev_state, prev_total
        nonlocal cum_capex_gross, cum_capex_subsidy, cum_capex_after, cum_installment
        nonlocal cum_elec_gross_year, cum_heat_gross_year, cum_mob_gross_year

        costs = _cost(state)
        rung_total = sum(costs)
        delta_gross_year = prev_total - rung_total

        layer_gross_eur, layer_subsidy_eur, layer_after_eur, layer_note = layer_capex
        delta_installment = annuity(layer_after_eur, ctx.financing_apr, ctx.financing_term_months)

        cum_capex_gross += layer_gross_eur
        cum_capex_subsidy += layer_subsidy_eur
        cum_capex_after += layer_after_eur
        cum_installment += delta_installment

        # Bucket attribution
        if layer_bucket == "electricity":
            cum_elec_gross_year += delta_gross_year
        elif layer_bucket == "heating":
            cum_heat_gross_year += delta_gross_year
        else:
            cum_mob_gross_year += delta_gross_year

        # Cumulative gross monthly saving (after_payoff)
        saving_after_payoff = (
            cum_elec_gross_year + cum_heat_gross_year + cum_mob_gross_year
        ) / 12.0

        # Cumulative net monthly saving
        monthly_saving = saving_after_payoff - cum_installment

        # Cumulative capex
        # Build subsidy_note from all layers so far
        subsidy_note = _build_subsidy_note(
            rec_pv_kwp=rec_pv_kwp,
            existing_pv_kwp=nh.existing.pv_kwp,
            pv_per_kwp_eur=ctx.pv_per_kwp_eur,
            rec_batt_kwh=rec_batt_kwh,
            existing_batt_kwh=nh.existing.battery_kwh,
            battery_per_kwh_eur=ctx.battery_per_kwh_eur,
            hp_included="heatpump" in scenario_id or scenario_id == "full-bundle",
            hp_gross=ctx.heatpump_fixed_eur,
            hp_subsidy=layer_subsidy_eur
            if layer_bucket == "heating"
            else (
                ctx.heatpump_fixed_eur * hp_rate
                if ("heatpump" in scenario_id or scenario_id == "full-bundle") and offer_hp
                else 0.0
            ),
            ev_included=state.ev_charger and offer_ev,
            wallbox_fixed_eur=ctx.wallbox_fixed_eur,
        )

        capex = Capex(
            gross_eur=cum_capex_gross,
            subsidy_eur=cum_capex_subsidy,
            after_subsidy_eur=cum_capex_after,
            subsidy_note=subsidy_note,
        )

        breakdown = Breakdown(
            electricity_eur_month=cum_elec_gross_year / 12.0,
            heating_eur_month=cum_heat_gross_year / 12.0,
            mobility_eur_month=cum_mob_gross_year / 12.0,
        )

        bev_month = _break_even_month(
            monthly_saving_eur=monthly_saving,
            saving_after_payoff_eur=saving_after_payoff,
            term_months=ctx.financing_term_months,
        )

        # Confidence only on the LAST / best rung; placeholder for others
        # (filled in by engine.recommend after the best rung is determined)
        placeholder_conf = Confidence(
            band_eur=0.0,
            low_eur=monthly_saving,
            high_eur=monthly_saving,
            biggest_driver="<pending>",
        )

        payback_note = f"Payback in month {bev_month}; after loan: +€{saving_after_payoff:.0f}/mo"

        prev_state = state  # noqa: F841 (outer scope update via nonlocal)
        prev_total = rung_total

        return ScenarioResult(
            scenario_id=scenario_id,
            label=label_str,
            breakdown=breakdown,
            capex=capex,
            installment_eur_month=cum_installment,
            monthly_saving_eur=monthly_saving,
            saving_after_payoff_eur=saving_after_payoff,
            break_even_month=bev_month,
            confidence=placeholder_conf,
            payback_note=payback_note,
        )

    # Rung 1 — Solar
    results.append(
        _make_rung(
            "☀️ Solar",
            "solar",
            r1,
            "electricity",
            _capex_solar(
                rec_pv_kwp=rec_pv_kwp,
                existing_pv_kwp=nh.existing.pv_kwp,
                pv_per_kwp_eur=ctx.pv_per_kwp_eur,
            ),
        )
    )

    # Rung 2 — Battery
    results.append(
        _make_rung(
            "☀️ Solar + 🔋 Battery",
            "solar-battery",
            r2,
            "electricity",
            _capex_battery(
                rec_batt_kwh=rec_batt_kwh,
                existing_batt_kwh=nh.existing.battery_kwh,
                battery_per_kwh_eur=ctx.battery_per_kwh_eur,
            ),
        )
    )

    # Rung 3 — Heat pump (optional)
    if offer_hp and r3 is not None:
        results.append(
            _make_rung(
                "☀️ Solar + 🔋 Battery + ♨️ Heat pump",
                "solar-battery-heatpump",
                r3,
                "heating",
                _capex_heatpump(
                    heatpump_fixed_eur=ctx.heatpump_fixed_eur,
                    hp_rate=hp_rate,
                ),
            )
        )

    # Rung 4 — EV charger (optional)
    if offer_ev and r4 is not None:
        results.append(
            _make_rung(
                "☀️ Solar + 🔋 Battery"
                + (" + ♨️ Heat pump" if offer_hp else "")
                + " + 🚗 EV charger",
                "full-bundle",
                r4,
                "mobility",
                _capex_ev(wallbox_fixed_eur=ctx.wallbox_fixed_eur),
            )
        )

    # --- Confidence band on best rung ---------------------------------------
    best_idx = max(range(len(results)), key=lambda i: results[i].monthly_saving_eur)
    best_result = results[best_idx]
    conf = _compute_confidence(
        base_headline=best_result.monthly_saving_eur,
        nh=nh,
        ctx=ctx,
        specific_yield=specific_yield,
        rec_pv_kwp=rec_pv_kwp,
        rec_batt_kwh=rec_batt_kwh,
        offer_hp=offer_hp,
        offer_ev=offer_ev,
        heating_baseline=heating_baseline,
        hp_rate=hp_rate,
    )
    results[best_idx] = best_result.model_copy(update={"confidence": conf})

    return results


# ---------------------------------------------------------------------------
# HP offer logic
# ---------------------------------------------------------------------------


def _is_old_hp(nh: NormalisedHousehold) -> bool:
    """True if the household has an existing heat pump (Case B)."""
    return any(
        v is not None
        for v in (
            nh.existing.heatpump_year,
            nh.existing.heatpump_power_kw,
            nh.existing.heatpump_scop,
        )
    )


def _should_offer_hp(nh: NormalisedHousehold) -> bool:
    """True if a heat-pump upgrade is offered (not already modern).

    Modern HP = year given AND age < HP_OFFER_AGE_THRESHOLD_YEARS.
    If no year given but HP present, we default to offering (age unknown → upgrade eligible).
    """
    import datetime

    if not _is_old_hp(nh):
        return True  # No existing HP → Case A fossil → offer

    year = nh.existing.heatpump_year
    if year is None:
        return True  # HP present but year unknown → offer Case B

    age = datetime.date.today().year - year
    return age >= HP_OFFER_AGE_THRESHOLD_YEARS


# ---------------------------------------------------------------------------
# Helper: cumulative subsidy note
# ---------------------------------------------------------------------------


def _build_subsidy_note(
    *,
    rec_pv_kwp: float,
    existing_pv_kwp: float,
    pv_per_kwp_eur: float,
    rec_batt_kwh: float,
    existing_batt_kwh: float,
    battery_per_kwh_eur: float,
    hp_included: bool,
    hp_gross: float,
    hp_subsidy: float,
    ev_included: bool,
    wallbox_fixed_eur: float,
) -> str:
    parts = []
    added_pv = max(0.0, rec_pv_kwp - existing_pv_kwp)
    if added_pv > 0:
        parts.append(f"PV {added_pv:.1f} kWp; 0% VAT")
    added_batt = max(0.0, rec_batt_kwh - existing_batt_kwh)
    if added_batt > 0:
        parts.append(f"Battery {added_batt:.1f} kWh; 0% VAT")
    if hp_included and hp_gross > 0:
        after = hp_gross - hp_subsidy
        parts.append(f"HP €{hp_gross:,.0f} − KfW = €{after:,.0f}")
    if ev_included:
        parts.append(f"Wallbox €{wallbox_fixed_eur:,.0f}; 0% subsidy")
    return "; ".join(parts) if parts else "0% VAT (net prices)"