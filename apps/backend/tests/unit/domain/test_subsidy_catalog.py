"""Unit tests for the subsidy catalog resolver — zero network, zero Supabase (R9).

All tests use the offline fallback seed (identical to the migration rows).
"""
from __future__ import annotations

from datetime import date

import pytest

from app.domain.savings.subsidy_layer.catalog import (
    SubsidyContext,
    Subsidy,
    components_for_intake,
    resolve_subsidies,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def ctx_today() -> SubsidyContext:
    """SubsidyContext using offline fallback, resolved for today (2026-06-21)."""
    return resolve_subsidies(
        request_date=date(2026, 6, 21),
        supabase_url="",
        supabase_key="",
    )


@pytest.fixture
def ctx_after_bafa() -> SubsidyContext:
    """SubsidyContext for a date after BAFA Umweltbonus ended (AC5)."""
    return resolve_subsidies(
        request_date=date(2024, 1, 1),
        supabase_url="",
        supabase_key="",
    )


# ── AC2 / R7: every returned row has a non-null source_url ───────────────────

def test_all_rows_have_source_url(ctx_today: SubsidyContext) -> None:
    all_rows = [
        row
        for rows in ctx_today.by_component.values()
        for row in rows
    ]
    assert all_rows, "expected at least one row"
    for row in all_rows:
        assert row.source_url, f"{row.programme}/{row.component} missing source_url"
        assert row.source_url.startswith("https://"), f"source_url not https: {row.source_url}"


# ── AC3: heat_pump_a gets both base + speed bonus ────────────────────────────

def test_heat_pump_a_gets_base_and_speed_bonus(ctx_today: SubsidyContext) -> None:
    rows = ctx_today.for_component("heat_pump_a")
    programmes = {r.programme for r in rows}
    assert "kfw_458_base" in programmes
    assert "kfw_458_speed_bonus" in programmes
    rates = {r.programme: r.rate for r in rows}
    assert rates["kfw_458_base"] == pytest.approx(0.30)
    assert rates["kfw_458_speed_bonus"] == pytest.approx(0.20)


# ── AC4: heat_pump_b gets base only, no speed bonus (§5.3 / R4) ─────────────

def test_heat_pump_b_no_speed_bonus(ctx_today: SubsidyContext) -> None:
    rows = ctx_today.for_component("heat_pump_b")
    programmes = {r.programme for r in rows}
    assert "kfw_458_base" in programmes
    assert "kfw_458_speed_bonus" not in programmes


# ── AC5: BAFA row excluded after valid_until date ────────────────────────────

def test_bafa_ev_excluded_after_valid_until(ctx_after_bafa: SubsidyContext) -> None:
    ev_rows = ctx_after_bafa.for_component("ev_charger")
    assert len(ev_rows) == 0, "BAFA row should be gated out after 2023-12-17"


def test_bafa_ev_present_before_valid_until() -> None:
    ctx = resolve_subsidies(request_date=date(2023, 12, 17), supabase_url="", supabase_key="")
    ev_rows = ctx.for_component("ev_charger")
    assert len(ev_rows) == 1
    assert ev_rows[0].programme == "bafa_ev_umweltbonus"


# ── AC7: KfW cap arithmetic — €22k capex → €11k grant ───────────────────────

def test_compute_grant_case_a_22k_capex(ctx_today: SubsidyContext) -> None:
    # heat_pump_a: 30% + 20% = 50%, capped at 70%, absolute cap €21k
    # grant = min(0.50 × 22000, 21000) = min(11000, 21000) = 11000
    grant = ctx_today.compute_grant("heat_pump_a", 22000.0)
    assert grant == pytest.approx(11000.0)


def test_compute_grant_case_a_50k_capex(ctx_today: SubsidyContext) -> None:
    # grant = min(0.50 × 50000, 21000) = min(25000, 21000) = 21000
    grant = ctx_today.compute_grant("heat_pump_a", 50000.0)
    assert grant == pytest.approx(21000.0)


def test_compute_grant_case_b(ctx_today: SubsidyContext) -> None:
    # heat_pump_b: only base 30%, cap €21k
    # grant = min(0.30 × 22000, 21000) = 6600
    grant = ctx_today.compute_grant("heat_pump_b", 22000.0)
    assert grant == pytest.approx(6600.0)


# ── AC8: KfW 70% hard cap (combined rate never exceeds 0.70) ─────────────────

def test_combined_rate_capped_at_70_percent() -> None:
    kfw_url = "https://www.kfw.de/inlandsfoerderung/test"
    ctx = SubsidyContext(
        request_date=date(2026, 6, 21),
        by_component={
            "heat_pump_a": [
                Subsidy("kfw_458_base", "heat_pump_a", 0.30, 21000.0, kfw_url, date(2026, 1, 1), None),
                Subsidy("kfw_458_speed_bonus", "heat_pump_a", 0.20, 21000.0, kfw_url, date(2026, 1, 1), None),
                Subsidy("kfw_458_income_bonus", "heat_pump_a", 0.30, 21000.0, kfw_url, date(2026, 1, 1), None),
            ]
        },
    )
    # 30 + 20 + 30 = 80% → clamped to 70%
    assert ctx.combined_rate("heat_pump_a") == pytest.approx(0.70)


def test_combined_rate_below_cap(ctx_today: SubsidyContext) -> None:
    # heat_pump_b has only 30%, which is below the 70% cap
    assert ctx_today.combined_rate("heat_pump_b") == pytest.approx(0.30)


# ── components_for_intake (replace vs add logic) ─────────────────────────────

def test_fossil_replacement_maps_to_heat_pump_a() -> None:
    components = components_for_intake(
        replaces_fossil_heating=True,
        has_existing_heatpump=False,
        wants_pv=True,
        wants_battery=True,
        wants_ev_charger=True,
    )
    assert "heat_pump_a" in components
    assert "heat_pump_b" not in components
    assert "pv" in components
    assert "battery" in components
    assert "ev_charger" in components


def test_old_heatpump_maps_to_heat_pump_b() -> None:
    components = components_for_intake(
        has_existing_heatpump=True,
        wants_pv=False,
        wants_battery=False,
        wants_ev_charger=False,
    )
    assert "heat_pump_b" in components
    assert "heat_pump_a" not in components


def test_wants_heatpump_without_fossil_maps_to_heat_pump_a() -> None:
    # e.g. district heating / electric → new HP install — still gets Case A grant
    components = components_for_intake(
        wants_heatpump=True,
        replaces_fossil_heating=False,
        has_existing_heatpump=False,
        wants_pv=False,
        wants_battery=False,
        wants_ev_charger=False,
    )
    assert "heat_pump_a" in components
    assert "heat_pump_b" not in components


def test_no_heating_upgrade_requested() -> None:
    components = components_for_intake(
        wants_heatpump=False,
        replaces_fossil_heating=False,
        has_existing_heatpump=False,
        wants_pv=True,
        wants_battery=False,
        wants_ev_charger=False,
    )
    assert "heat_pump_a" not in components
    assert "heat_pump_b" not in components
    assert "pv" in components


# ── applied_assumptions: VAT rows included as informational citations ─────────

def test_applied_assumptions_includes_vat_row(ctx_today: SubsidyContext) -> None:
    # 0% VAT row has rate=0 but SHOULD appear as a citation so the user sees the source
    assumptions = ctx_today.applied_assumptions("pv")
    assert len(assumptions) == 1, "expected the 0% VAT row"
    assert assumptions[0]["rate"] == 0.0
    assert assumptions[0]["source"], "VAT row must have a source_url"


def test_applied_assumptions_heat_pump_a_has_source(ctx_today: SubsidyContext) -> None:
    assumptions = ctx_today.applied_assumptions("heat_pump_a")
    assert len(assumptions) == 2, "expected base + speed bonus"
    for a in assumptions:
        assert a["source"], "each assumption must have a source URL"


# ── compute_grant returns 0 for expired/missing component ────────────────────

def test_compute_grant_zero_for_expired_component(ctx_after_bafa: SubsidyContext) -> None:
    # BAFA is expired → no rows → grant is 0
    grant = ctx_after_bafa.compute_grant("ev_charger", 1200.0)
    assert grant == pytest.approx(0.0)


# ── compute_grant cap uses max(caps) not min ──────────────────────────────────

def test_compute_grant_uses_max_cap_not_min() -> None:
    kfw_url = "https://www.kfw.de/inlandsfoerderung/test"
    # Two rows: one with cap=21000 (KfW), one with cap=5000 (hypothetical smaller cap).
    # Combined rate = 50%, capex = 50000 → uncapped grant = 25000.
    # max(caps) = 21000 → grant = 21000.  (min(caps) would give wrong 5000)
    ctx = SubsidyContext(
        request_date=date(2026, 6, 21),
        by_component={
            "heat_pump_a": [
                Subsidy("kfw_458_base", "heat_pump_a", 0.30, 21000.0, kfw_url, date(2026, 1, 1), None),
                Subsidy("kfw_458_speed_bonus", "heat_pump_a", 0.20, 5000.0, kfw_url, date(2026, 1, 1), None),
            ]
        },
    )
    grant = ctx.compute_grant("heat_pump_a", 50000.0)
    assert grant == pytest.approx(21000.0), "should use max cap (21000), not min cap (5000)"


# ── KFW_MAX_RATE cap scoped to heat_pump only ────────────────────────────────

def test_rate_cap_not_applied_to_pv(ctx_today: SubsidyContext) -> None:
    # PV only has 0% VAT row → combined_rate should be 0.0 (not capped at 0.70)
    assert ctx_today.combined_rate("pv") == pytest.approx(0.0)
