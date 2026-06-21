"""Unit tests for the subsidy crawler gate logic — zero network, zero API keys."""
from __future__ import annotations

import pytest

from app.domain.savings.subsidy_layer.crawler import (
    CrawlResult,
    _validate_gate,
    refresh_federal,
)


# ── _validate_gate ────────────────────────────────────────────────────────────

def test_gate_passes_valid_new_row() -> None:
    proposed = {"programme": "kfw_458_base", "component": "heat_pump_a", "rate": 0.30}
    passes, note = _validate_gate(proposed, live_row=None, source_url="https://www.kfw.de/")
    assert passes
    assert note == "ok"


def test_gate_fails_rate_above_1() -> None:
    proposed = {"programme": "kfw_458_base", "component": "heat_pump_a", "rate": 1.5}
    passes, note = _validate_gate(proposed, live_row=None, source_url="https://www.kfw.de/")
    assert not passes
    assert "out of bounds" in note


def test_gate_fails_rate_below_0() -> None:
    proposed = {"programme": "kfw_458_base", "component": "heat_pump_a", "rate": -0.1}
    passes, note = _validate_gate(proposed, live_row=None, source_url="https://www.kfw.de/")
    assert not passes


def test_gate_fails_missing_source_url() -> None:
    proposed = {"programme": "kfw_458_base", "component": "heat_pump_a", "rate": 0.30}
    passes, note = _validate_gate(proposed, live_row=None, source_url="")
    assert not passes
    assert "source_url" in note


def test_gate_fails_http_source_url() -> None:
    proposed = {"programme": "kfw_458_base", "component": "heat_pump_a", "rate": 0.30}
    passes, note = _validate_gate(proposed, live_row=None, source_url="http://www.kfw.de/")
    assert not passes
    assert "source_url" in note


def test_gate_passes_small_rate_change() -> None:
    proposed = {"rate": 0.32}  # 30% → 32%, within ±25% tolerance
    live_row = {"rate": 0.30}
    passes, _ = _validate_gate(proposed, live_row, source_url="https://www.kfw.de/")
    assert passes


def test_gate_quarantines_large_rate_jump() -> None:
    proposed = {"rate": 0.60}  # 30% → 60%, jump of 0.30 > tolerance 0.25
    live_row = {"rate": 0.30}
    passes, note = _validate_gate(proposed, live_row, source_url="https://www.kfw.de/")
    assert not passes
    assert "jumped too far" in note


def test_gate_passes_zero_rate_new_row() -> None:
    # BAFA ended → rate=0 is valid (0 is within 0–1)
    proposed = {"rate": 0.0}
    passes, _ = _validate_gate(proposed, live_row=None, source_url="https://www.bafa.de/")
    assert passes


def test_gate_passes_zero_rate_vs_zero_live() -> None:
    proposed = {"rate": 0.0}
    live_row = {"rate": 0.0}
    passes, _ = _validate_gate(proposed, live_row, source_url="https://www.bafa.de/")
    assert passes


def test_gate_passes_rate_exactly_at_boundary() -> None:
    # Jump of exactly 0.25 should pass (tolerance is ≤ 0.25)
    proposed = {"rate": 0.55}
    live_row = {"rate": 0.30}
    passes, _ = _validate_gate(proposed, live_row, source_url="https://www.kfw.de/")
    assert passes


# ── refresh_federal no-op on missing keys ────────────────────────────────────

def test_refresh_federal_noop_missing_tavily_key() -> None:
    result = refresh_federal(
        tavily_key="",
        openai_key="sk-test",
        supabase_url="https://x.supabase.co",
        supabase_key="key",
    )
    assert isinstance(result, CrawlResult)
    assert result.promoted == 0
    assert result.errors > 0  # signals that it skipped, not crashed


def test_refresh_federal_noop_missing_openai_key() -> None:
    result = refresh_federal(
        tavily_key="tvly-test",
        openai_key="",
        supabase_url="https://x.supabase.co",
        supabase_key="key",
    )
    assert result.promoted == 0
    assert result.errors > 0


def test_refresh_federal_noop_missing_supabase() -> None:
    result = refresh_federal(
        tavily_key="tvly-test",
        openai_key="sk-test",
        supabase_url="",
        supabase_key="",
    )
    assert result.promoted == 0
    assert result.errors > 0


def test_crawl_result_as_dict() -> None:
    r = CrawlResult(promoted=3, quarantined=1, errors=0, crawled_at="2026-06-21T00:00:00+00:00")
    d = r.as_dict()
    assert d["promoted"] == 3
    assert d["quarantined"] == 1
    assert d["errors"] == 0
    assert "crawled_at" in d
