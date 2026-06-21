"""Recommendation engine — orchestrates the pure savings ladder (F10, F11, F27).

Owner: Lukas (engine)
Feature ID: F06 (solar) … F11 (financing) · F27 (three-strategy recommend)

Pure: takes a Household + PricingContext, returns a Recommendation.
No I/O — adapters/services supply the context.

F05 normalisation is called as the first step; the ladder is built by
scenarios.build_ladder.  F27 selects the best rung and constructs the
upsell and assumptions list.
"""

from __future__ import annotations

from app.domain.constants import SPECIFIC_YIELD_FALLBACK
from app.domain.models import (
    Assumption,
    Household,
    PricingContext,
    Recommendation,
    Upsell,
)
from app.domain.savings.intake import normalise_household
from app.domain.savings.scenarios import build_ladder


def recommend(
    household: Household,
    ctx: PricingContext,
    specific_yield: float = SPECIFIC_YIELD_FALLBACK,
) -> Recommendation:
    """Compute the ranked recommendation.

    Parameters
    ----------
    household:
        Validated intake data (Pydantic model).
    ctx:
        Resolved prices / tariffs / capex from the price catalog.
    specific_yield:
        Annual PV yield in kWh/kWp for this location.
        Defaults to the PVGIS Germany fallback (980 kWh/kWp/yr).
        The resolver (F12) injects the site-specific value.

    Returns
    -------
    Recommendation
        The full advisor output including the best scenario, the 2–4
        cumulative rungs, an upsell, and the assumptions list.
    """
    nh = normalise_household(household, ctx)

    alternatives = build_ladder(nh, ctx, specific_yield)

    # F27: best = rung with highest monthly_saving_eur
    best_idx = max(range(len(alternatives)), key=lambda i: alternatives[i].monthly_saving_eur)
    best = alternatives[best_idx]

    # Upsell: from the rung just below best to best
    # If best is the first rung, upsell from an empty baseline (delta = best.monthly_saving itself)
    if best_idx > 0:
        from_rung = alternatives[best_idx - 1]
        upsell = Upsell(
            from_scenario_id=from_rung.scenario_id,
            to_scenario_id=best.scenario_id,
            delta_eur_month=best.monthly_saving_eur - from_rung.monthly_saving_eur,
            reason_md=(
                f"Upgrading from **{from_rung.scenario_id}** to **{best.scenario_id}** "
                f"adds **+€{best.monthly_saving_eur - from_rung.monthly_saving_eur:.0f}/mo** "
                f"because the remaining layers still displace high fossil costs."
            ),
        )
    else:
        upsell = Upsell(
            from_scenario_id="none",
            to_scenario_id=best.scenario_id,
            delta_eur_month=best.monthly_saving_eur,
            reason_md=(
                f"The **{best.scenario_id}** package delivers "
                f"**+€{best.monthly_saving_eur:.0f}/mo** from day one."
            ),
        )

    # Engine-level assumptions (complement intake assumptions)
    engine_assumptions: list[Assumption] = [
        Assumption(
            field="specific_yield_kwh_per_kwp",
            value=f"{specific_yield:.0f} kWh/kWp",
            source="PVGIS fallback (F03 §8.2)"
            if specific_yield == SPECIFIC_YIELD_FALLBACK
            else "PVGIS site-specific",
            editable=True,
        ),
        Assumption(
            field="autarky_pv_only",
            value="0.30",
            source="F03 physics default §3.2",
            editable=True,
        ),
        Assumption(
            field="autarky_with_battery",
            value="0.60",
            source="F03 physics default §3.2",
            editable=True,
        ),
        Assumption(
            field="kfw_hp_subsidy",
            value="50% (fossil→HP) / 30% (old-HP upgrade)",
            source="KfW 458 programme defaults (F03 §3.2)",
            editable=True,
        ),
        Assumption(
            field="financing_apr",
            value=f"{ctx.financing_apr * 100:.1f}%",
            source="Cloover labelled assumption",
            editable=True,
        ),
        Assumption(
            field="financing_term_months",
            value=f"{ctx.financing_term_months} months",
            source="Cloover labelled assumption",
            editable=True,
        ),
        Assumption(
            field="pv_sizing_heuristic",
            value="ceil₀.₅(total_demand × 0.80 / specific_yield)",
            source="F06 engine default; covers ~80% of total electric demand",
            editable=False,
        ),
        Assumption(
            field="battery_sizing_heuristic",
            value="round(annual_kwh / 1000), clamp 5..10 kWh",
            source="F07 engine default",
            editable=False,
        ),
    ]

    all_assumptions = list(nh.assumptions) + engine_assumptions

    return Recommendation(
        best=best,
        alternatives=alternatives,
        upsell=upsell,
        current_monthly_spend_eur=nh.current_monthly_spend_eur,
        explanation_md="<generated by F16 LLM>",
        proposal_copy_md="<generated by F16 LLM>",
        assumptions=all_assumptions,
    )