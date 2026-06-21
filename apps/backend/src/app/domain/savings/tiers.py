"""Three packaged tiers (low / middle / high) for the dashboard offer cards.

Owner: engine
Feature ID: F27 (three-strategy recommend) — dashboard offer view

Pure: takes the cumulative ladder (alternatives[]) plus the financing term and
returns exactly three Tier offers, designed to be displayed side-by-side:

- ``low``    — cost-efficient entry: the ☀️+🔋 solar+battery rung (bundles storage
               with the panels), falling back to bare solar on a 2-rung ladder.
- ``middle`` — best-value milestone: strongest net monthly saving *below* the
               full bundle.
- ``high``   — future-proof (deepest rung): the full bundle, headlined by the
               cumulative saving over LIFETIME_HORIZON_YEARS plus the permanent
               €/mo after the loan is paid off.

The tiers are derived entirely from existing ScenarioResult numbers — no new
money math, so every € figure stays grounded in the ladder (numeric authority
never moves to the LLM prose).
"""

from __future__ import annotations

from app.domain.constants import LIFETIME_HORIZON_YEARS
from app.domain.models import ScenarioResult, Tier


def _lifetime_saving_eur(rung: ScenarioResult, term_months: int, horizon_months: int) -> float:
    """Cumulative NET saving over the horizon.

    During the loan (``term_months``) the household nets ``monthly_saving_eur``;
    afterwards it nets the full ``saving_after_payoff_eur`` for the remaining
    months of the horizon.
    """
    paying_months = min(term_months, horizon_months)
    free_months = max(0, horizon_months - term_months)
    return rung.monthly_saving_eur * paying_months + rung.saving_after_payoff_eur * free_months


def _select_indices(n: int) -> tuple[int, int, int]:
    """Pick (low, middle, high) rung indices from an n-rung ladder.

    high = deepest bundle; middle = a rung strictly between when one exists.

    The Starter (low) tier bundles storage with the panels: it maps to the
    ☀️+🔋 solar+battery rung (index 1) whenever the ladder is deep enough to keep
    a distinct higher tier above it.  For a 2-rung ladder (household that already
    has a heat pump *and* a charger, so solar+battery is itself the top rung) the
    Starter degrades to bare solar so the three cards stay distinct.

    Degrades gracefully for short ladders (the middle card may coincide with
    another tier when fewer than three rungs exist).
    """
    high_i = n - 1
    low_i = 1 if n >= 3 else 0  # Starter = solar+battery when a higher tier exists
    if n >= 3:
        mid_i = n // 2  # the middle rung is resolved by net-saving below
    elif n == 2:
        mid_i = 1  # only two distinct rungs → middle coincides with high
    else:
        mid_i = 0
    return low_i, mid_i, high_i


def build_tiers(alternatives: list[ScenarioResult], term_months: int) -> list[Tier]:
    """Build the three dashboard tiers from the cumulative ladder."""
    horizon_months = LIFETIME_HORIZON_YEARS * 12
    rungs = alternatives
    n = len(rungs)

    low_i, _, high_i = _select_indices(n)
    low = rungs[low_i]
    high = rungs[high_i]

    # Middle = best net-saving rung strictly between low and high; fall back to
    # the high rung when the ladder is too short to have a distinct middle.
    mids = rungs[low_i + 1 : high_i]
    middle = max(mids, key=lambda r: r.monthly_saving_eur) if mids else high

    def _tier(
        tier_id: str,
        name: str,
        tagline: str,
        rung: ScenarioResult,
        headline_eur: float,
        headline_caption: str,
        rationale_md: str,
    ) -> Tier:
        return Tier(
            id=tier_id,  # type: ignore[arg-type]
            name=name,
            tagline=tagline,
            scenario_id=rung.scenario_id,
            label=rung.label,
            capex_after_subsidy_eur=rung.capex.after_subsidy_eur,
            installment_eur_month=rung.installment_eur_month,
            monthly_saving_eur=rung.monthly_saving_eur,
            saving_after_payoff_eur=rung.saving_after_payoff_eur,
            break_even_month=rung.break_even_month,
            lifetime_years=LIFETIME_HORIZON_YEARS,
            lifetime_saving_eur=round(_lifetime_saving_eur(rung, term_months, horizon_months), 2),
            headline_eur=round(headline_eur, 2),
            headline_caption=headline_caption,
            rationale_md=rationale_md,
        )

    low_tier = _tier(
        "low",
        "Starter",
        "Lowest upfront investment — solid baseline savings.",
        low,
        headline_eur=low.saving_after_payoff_eur,
        headline_caption=(
            f"€/month after payoff · from €{low.capex.after_subsidy_eur:,.0f} investment"
        ),
        rationale_md=(
            f"The most affordable entry point with just €{low.capex.after_subsidy_eur:,.0f} capital "
            f"and a €{low.installment_eur_month:.0f}/month installment. After payoff it saves a steady "
            f"€{low.saving_after_payoff_eur:.0f}/month — the lowest-risk step into the energy transition."
        ),
    )

    middle_tier = _tier(
        "middle",
        "Best Value",
        "The sweet spot between investment and savings.",
        middle,
        headline_eur=middle.saving_after_payoff_eur,
        headline_caption=(
            f"€/month after payoff · €{middle.capex.after_subsidy_eur:,.0f} investment"
        ),
        rationale_md=(
            f"The best value for money: for €{middle.capex.after_subsidy_eur:,.0f} you get "
            f"a steady €{middle.saving_after_payoff_eur:.0f}/month — around "
            f"€{_lifetime_saving_eur(middle, term_months, horizon_months):,.0f} in total savings over "
            f"{LIFETIME_HORIZON_YEARS} years."
        ),
    )

    high_lifetime = _lifetime_saving_eur(high, term_months, horizon_months)
    high_tier = _tier(
        "high",
        "Future-proof",
        "An investment in the future — maximum total savings.",
        high,
        headline_eur=high_lifetime,
        headline_caption=(
            f"over {LIFETIME_HORIZON_YEARS} years · then €{high.saving_after_payoff_eur:.0f}"
            f"/month for life"
        ),
        rationale_md=(
            f"The full package: around €{high_lifetime:,.0f} in total savings over "
            f"{LIFETIME_HORIZON_YEARS} years and then a steady "
            f"€{high.saving_after_payoff_eur:.0f}/month — maximum independence."
        ),
    )

    return [low_tier, middle_tier, high_tier]
