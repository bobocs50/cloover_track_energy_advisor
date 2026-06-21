"""Dashboard three-tier derivation (low / middle / high) from the savings ladder."""

from __future__ import annotations

from app.domain.constants import LIFETIME_HORIZON_YEARS
from app.domain.models import (
    Breakdown,
    Capex,
    Confidence,
    ScenarioResult,
)
from app.domain.savings.tiers import build_tiers


def _rung(
    scenario_id: str,
    *,
    capex_after: float,
    installment: float,
    net: float,
    after_payoff: float,
    bev: int,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        label=scenario_id,
        breakdown=Breakdown(
            electricity_eur_month=0.0, heating_eur_month=0.0, mobility_eur_month=0.0
        ),
        capex=Capex(
            gross_eur=capex_after,
            subsidy_eur=0.0,
            after_subsidy_eur=capex_after,
            subsidy_note="",
        ),
        installment_eur_month=installment,
        monthly_saving_eur=net,
        saving_after_payoff_eur=after_payoff,
        break_even_month=bev,
        confidence=Confidence(band_eur=0.0, low_eur=net, high_eur=net, biggest_driver="x"),
        payback_note="",
    )


def _ladder() -> list[ScenarioResult]:
    return [
        _rung("solar", capex_after=13_775, installment=109, net=-18, after_payoff=91, bev=216),
        _rung("solar-battery", capex_after=18_000, installment=142, net=-12, after_payoff=130, bev=180),
        _rung("solar-battery-heatpump", capex_after=31_075, installment=246, net=2, after_payoff=248, bev=1),
        _rung("full-bundle", capex_after=32_275, installment=255, net=137, after_payoff=392, bev=1),
    ]


def test_returns_three_tiers_in_low_middle_high_order() -> None:
    tiers = build_tiers(_ladder(), term_months=180)
    assert [t.id for t in tiers] == ["low", "middle", "high"]


def test_low_is_entry_high_is_full_bundle() -> None:
    tiers = build_tiers(_ladder(), term_months=180)
    low, _middle, high = tiers
    assert low.scenario_id == "solar"
    assert high.scenario_id == "full-bundle"


def test_middle_is_best_partial_bundle_excluding_full() -> None:
    # Of the in-between rungs, the heat-pump rung has the strongest net saving.
    tiers = build_tiers(_ladder(), term_months=180)
    assert tiers[1].scenario_id == "solar-battery-heatpump"


def test_high_headline_is_lifetime_and_matches_formula() -> None:
    term = 180
    horizon = LIFETIME_HORIZON_YEARS * 12  # 240
    tiers = build_tiers(_ladder(), term_months=term)
    high = tiers[2]
    expected = 137 * term + 392 * (horizon - term)
    assert high.lifetime_saving_eur == expected
    assert high.headline_eur == high.lifetime_saving_eur  # high leads with the long-term number


def test_tier_numbers_are_grounded_in_their_rung() -> None:
    ladder = _ladder()
    by_id = {r.scenario_id: r for r in ladder}
    for tier in build_tiers(ladder, term_months=180):
        rung = by_id[tier.scenario_id]
        assert tier.capex_after_subsidy_eur == rung.capex.after_subsidy_eur
        assert tier.monthly_saving_eur == rung.monthly_saving_eur
        assert tier.saving_after_payoff_eur == rung.saving_after_payoff_eur
        assert tier.break_even_month == rung.break_even_month


def test_short_ladder_still_yields_three_tiers() -> None:
    # Household that already has HP + charger → only the two electricity rungs.
    short = _ladder()[:2]
    tiers = build_tiers(short, term_months=180)
    assert [t.id for t in tiers] == ["low", "middle", "high"]
    assert tiers[0].scenario_id == "solar"
    assert tiers[2].scenario_id == "solar-battery"
