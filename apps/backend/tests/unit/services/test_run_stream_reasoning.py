"""Unit tests for the deterministic cross-effect reasoning events.

`_reasoning_events` must derive every € figure from the engine result (a
ScenarioResult / Capex) — it invents nothing. These tests load the golden
Recommendation fixture and assert the emitted reasoning is grounded in it.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.api.schemas.pipeline import EventBuilder
from app.domain.models import (
    Address,
    CarType,
    FuelType,
    HeatingInput,
    Household,
    MobilityInput,
    Recommendation,
)
from app.services.run_stream import _reasoning_events, _signed_eur

_FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "demo-detached.json"


def _rec() -> Recommendation:
    return Recommendation.model_validate(json.loads(_FIXTURE.read_text(encoding="utf-8")))


def _household(
    *,
    existing_heatpump_year: int | None = None,
) -> Household:
    return Household(
        address=Address(street="Invalidenstraße", house_no="116", city="Berlin"),
        plz="10115",
        floor_area_m2=140,
        building_year=1985,
        occupants=3,
        electricity_eur_month=95,
        heating=HeatingInput(fuel=FuelType.OIL, eur_month=180),
        mobility=MobilityInput(kind=CarType.PETROL, km_month=1200),
        existing_heatpump_year=existing_heatpump_year,
    )


def _by_layer(events: list, layer: str) -> list:
    return [e for e in events if e.layer_id == layer]


def test_subsidy_event_is_grounded_in_capex() -> None:
    rec = _rec()
    events = _reasoning_events(EventBuilder("t"), rec, _household())
    subsidy = _by_layer(events, "subsidy")
    assert subsidy, "expected a subsidy reasoning event"
    payload = subsidy[0].payload or {}
    # Numbers copied verbatim from the engine result — never invented.
    assert payload["subsidyEur"] == round(rec.best.capex.subsidy_eur)
    assert payload["afterSubsidyEur"] == round(rec.best.capex.after_subsidy_eur)
    assert payload["breakEvenMonth"] == rec.best.break_even_month
    assert payload["offerEffect"] == rec.best.capex.subsidy_note


def test_fossil_household_gets_conversion_reasoning() -> None:
    events = _reasoning_events(EventBuilder("t"), _rec(), _household())
    hp = _by_layer(events, "heat_pump")
    assert hp, "expected a heat-pump reasoning event"
    assert "conversion" in hp[0].title.lower()


def test_old_heatpump_household_gets_replacement_reasoning() -> None:
    events = _reasoning_events(
        EventBuilder("t"), _rec(), _household(existing_heatpump_year=2005)
    )
    hp = _by_layer(events, "heat_pump")
    assert hp, "expected a heat-pump reasoning event"
    assert "replacement" in hp[0].title.lower()


def test_signed_eur_never_double_signs() -> None:
    # A negative rung delta must read '-€101', never '+€-101' or '€-101'.
    assert _signed_eur(-101.0) == "-€101"
    assert _signed_eur(42.0) == "+€42"
    assert _signed_eur(0.0) == "+€0"
    assert _signed_eur(-0.4) == "+€0"  # rounds to 0, no '-€0'


def test_reasoning_titles_have_no_double_sign() -> None:
    # Every emitted reasoning title must be free of the '+€-' / '€-' artefacts.
    events = _reasoning_events(
        EventBuilder("t"), _rec(), _household(existing_heatpump_year=2005)
    )
    for e in events:
        assert "+€-" not in e.title, e.title
        assert "€-" not in e.title, e.title


def test_solar_battery_delta_matches_ladder() -> None:
    rec = _rec()
    events = _reasoning_events(EventBuilder("t"), rec, _household())
    battery = _by_layer(events, "battery")
    assert battery, "expected a battery reasoning event"
    expected = rec.alternatives[1].monthly_saving_eur - rec.alternatives[0].monthly_saving_eur
    assert (battery[0].payload or {})["deltaEurMonth"] == round(expected, 1)
