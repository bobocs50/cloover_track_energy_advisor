"""Unit tests for permit_layer checks — hardcoded rules need no HTTP mocking."""
from unittest.mock import MagicMock, patch

from app.domain.savings.permit_layer.checks import (
    PERMIT_CATEGORY_ORDER,
    check_battery_install,
    check_battery_mastr,
    check_denkmal_heatpump,
    check_denkmal_solar,
    check_ev_parking,
    check_ev_weg,
    check_hp_geg,
    check_mastr,
    group_by_category,
)

# ---------------------------------------------------------------------------
# Hardcoded rules — no HTTP needed
# ---------------------------------------------------------------------------

def test_battery_install_always_pass() -> None:
    check = check_battery_install()
    assert check.status == "pass"
    assert check.product == "battery"
    assert check.id == "battery_install"


def test_battery_mastr_always_info() -> None:
    check = check_battery_mastr()
    assert check.status == "info"
    assert check.product == "battery"
    assert check.cited_clause is not None


def test_hp_geg_old_boiler_pass() -> None:
    check = check_hp_geg(building_year=2000, fuel_type="GAS")
    assert check.status == "pass"  # 2024-2000 = 24 years ≥ 20


def test_hp_geg_new_boiler_warn() -> None:
    check = check_hp_geg(building_year=2015, fuel_type="OIL")
    assert check.status == "warn"  # 2024-2015 = 9 years < 20


def test_hp_geg_non_fossil_always_pass() -> None:
    check = check_hp_geg(building_year=2020, fuel_type="HEAT_PUMP")
    assert check.status == "pass"


def test_hp_geg_pass_has_clause() -> None:
    check = check_hp_geg(building_year=1990, fuel_type="OIL")
    assert check.status == "pass"
    assert check.cited_clause is not None
    assert "§72" in (check.cited_clause or "")


# ---------------------------------------------------------------------------
# EV parking — user flag short-circuits HTTP
# ---------------------------------------------------------------------------

def test_ev_parking_user_confirmed() -> None:
    check = check_ev_parking(lat=49.52, lng=9.32, has_private_parking=True)
    assert check.status == "pass"
    assert "confirmed" in check.label.lower()


def test_ev_parking_no_parking_no_osm() -> None:
    # Mock OSM returning empty
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"elements": []}
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_resp):
        check = check_ev_parking(lat=49.52, lng=9.32, has_private_parking=False)

    assert check.status == "fail"
    assert check.product == "ev_charger"


# ---------------------------------------------------------------------------
# EV WEG — apartment detection
# ---------------------------------------------------------------------------

def test_ev_weg_single_family() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"elements": []}
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_resp):
        check = check_ev_weg(lat=49.52, lng=9.32)

    assert check.status == "pass"


def test_ev_weg_apartment_warns() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "elements": [{"tags": {"building": "apartments"}}]
    }
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_resp):
        check = check_ev_weg(lat=49.52, lng=9.32)

    assert check.status == "warn"
    assert "WEG" in check.detail


# ---------------------------------------------------------------------------
# MaStR — neighbour count thresholds
# ---------------------------------------------------------------------------

def test_mastr_no_keys_warns() -> None:
    # No Supabase, no Kendo (mocked to fail), no Tavily → warn
    kendo_fail = MagicMock()
    kendo_fail.status_code = 500
    with patch("httpx.post", return_value=kendo_fail):
        check = check_mastr("74722")
    assert check.status == "warn"
    assert check.product == "solar"


def test_mastr_supabase_high_count_passes() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"count": 67}]
    mock_resp.raise_for_status.return_value = None
    with patch("httpx.get", return_value=mock_resp):
        check = check_mastr("74722", supabase_url="https://x.supabase.co", supabase_key="key")
    assert check.status == "pass"
    assert "67" in check.label


def test_mastr_supabase_low_count_warns() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"count": 3}]
    mock_resp.raise_for_status.return_value = None
    with patch("httpx.get", return_value=mock_resp):
        check = check_mastr("74722", supabase_url="https://x.supabase.co", supabase_key="key")
    assert check.status == "warn"


def test_mastr_page_scrape_high_count_passes() -> None:
    # Tier 2 is now a GET scrape of the MaStR page looking for "Total":142 in HTML
    kendo_resp = MagicMock()
    kendo_resp.status_code = 200
    kendo_resp.text = 'some html ... "Total":142 ... more html'
    with patch("httpx.get", return_value=kendo_resp):
        check = check_mastr("74722")
    assert check.status == "pass"
    assert "142" in check.label


def test_mastr_tavily_fallback_high_count_passes() -> None:
    kendo_fail = MagicMock()
    kendo_fail.status_code = 403
    mock_tavily = MagicMock()
    mock_tavily.search.return_value = {
        "results": [{"content": "Es sind 67 Solaranlagen in PLZ 74722 registriert.", "url": "https://example.com"}]
    }
    with patch("httpx.post", return_value=kendo_fail):
        with patch("tavily.TavilyClient", return_value=mock_tavily):
            check = check_mastr("74722", tavily_api_key="test-key")
    assert check.status == "pass"
    assert "67" in check.label


def test_mastr_all_sources_fail_graceful() -> None:
    kendo_fail = MagicMock()
    kendo_fail.status_code = 500
    with patch("httpx.post", return_value=kendo_fail):
        with patch("tavily.TavilyClient", side_effect=Exception("timeout")):
            check = check_mastr("74722", tavily_api_key="test-key")
    assert check.status == "warn"


# ---------------------------------------------------------------------------
# Denkmal — WMS + OSM logic
# ---------------------------------------------------------------------------

def test_denkmal_solar_wms_not_listed() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"features": []}
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_resp):
        check = check_denkmal_solar(lat=48.14, lng=11.58, bundesland="Bayern")

    assert check.status == "pass"
    assert "Bayern" in check.source_name


def test_denkmal_solar_wms_listed_blocks() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"properties": {"bezeichnung": "Altes Rathaus"}}]
    }
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_resp):
        check = check_denkmal_solar(lat=48.14, lng=11.58, bundesland="Bayern")

    assert check.status == "fail"
    assert "Altes Rathaus" in check.label


def test_denkmal_solar_bw_wms_not_listed() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"features": []}
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_resp):
        # BW now has a WMS endpoint → pass when not listed
        check = check_denkmal_solar(lat=48.77, lng=9.18, bundesland="Baden-Württemberg")

    assert check.status == "pass"
    assert "Baden-Württemberg" in check.source_name


def test_denkmal_heatpump_listed_is_warn_not_fail() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "features": [{"properties": {"bezeichnung": "Denkmal"}}]
    }
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_resp):
        check = check_denkmal_heatpump(lat=48.14, lng=11.58, bundesland="Bayern")

    # HP on listed building → warn (approval sometimes granted), NOT fail
    assert check.status == "warn"
    assert check.product == "heatpump"


# ---------------------------------------------------------------------------
# Check depth: category, source provenance, and reasoning fields
# ---------------------------------------------------------------------------

def test_static_check_carries_category_and_reasoning() -> None:
    check = check_battery_install()
    assert check.category == "Battery permissions"
    assert check.source_type == "static_rule"
    assert check.why_it_matters  # non-empty deterministic reasoning
    assert check.offer_effect


def test_source_type_reflects_origin() -> None:
    # static rule (GEG) vs live internet (Denkmal WMS) vs supabase cache (MaStR)
    geg = check_hp_geg(building_year=2000, fuel_type="GAS")
    assert geg.source_type == "static_rule"

    wms = MagicMock()
    wms.json.return_value = {"features": []}
    wms.raise_for_status.return_value = None
    with patch("httpx.get", return_value=wms):
        denkmal = check_denkmal_solar(lat=48.14, lng=11.58, bundesland="Bayern")
    assert denkmal.source_type == "live_internet"
    assert denkmal.confidence == 0.9

    cache = MagicMock()
    cache.json.return_value = [{"count": 67}]
    cache.raise_for_status.return_value = None
    with patch("httpx.get", return_value=cache):
        mastr = check_mastr("74722", supabase_url="https://x.supabase.co", supabase_key="k")
    assert mastr.source_type == "supabase_cache"


def test_categories_map_to_canonical_set() -> None:
    checks = [
        check_battery_install(),
        check_battery_mastr(),
        check_hp_geg(building_year=2000, fuel_type="GAS"),
    ]
    for ch in checks:
        assert ch.category in PERMIT_CATEGORY_ORDER


def test_group_by_category_orders_and_omits_empty() -> None:
    grouped = group_by_category(
        [check_battery_install(), check_hp_geg(building_year=2000, fuel_type="GAS")]
    )
    # Canonical order preserved; empty categories (Location/Solar/EV) omitted.
    assert list(grouped.keys()) == ["Heat pump permissions", "Battery permissions"]
