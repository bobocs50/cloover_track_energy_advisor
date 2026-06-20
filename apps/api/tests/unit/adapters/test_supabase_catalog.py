"""F04 schema, seed, and server-side Supabase client tests."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.adapters.supabase import get_supabase_client
from app.core.config import Settings

ROOT = Path(__file__).parents[5]
MIGRATION = ROOT / "supabase/migrations/202606200001_f04_schema.sql"
SEED = ROOT / "supabase/seed.sql"

EXPECTED_TABLE_COLUMNS = {
    "reference_plz": {
        "plz",
        "lat",
        "lon",
        "specific_yield",
        "retail_price",
        "grid_fee",
        "climate_zone",
        "mastr_count",
    },
    "price_catalog": {
        "component",
        "tier",
        "unit",
        "unit_price",
        "source",
        "valid_from",
    },
    "cache_pvgis": {
        "lat",
        "lon",
        "tilt",
        "azimuth",
        "kwp",
        "payload_json",
        "fetched_at",
    },
    "cache_dynprice": {"market_area", "day", "payload_json", "fetched_at"},
    "advise_run": {
        "id",
        "household_json",
        "options_json",
        "recommendation_json",
        "created_at",
    },
    "proposal": {"id", "advise_run_id", "copy_md", "created_at"},
    "denkmal_seed": {"plz", "flag"},
    "mastr_seed": {"plz", "count"},
}

EXPECTED_PRICES = {
    ("pv_per_kwp", "SMALL"): "1450.0",
    ("pv_per_kwp", "LARGE"): "1300.0",
    ("battery_per_kwh", "STANDARD"): "700.0",
    ("heatpump_fixed", "STANDARD"): "22000.0",
    ("wallbox_fixed", "STANDARD"): "1200.0",
    ("oil_per_litre", "STANDARD"): "1.10",
    ("gas_per_kwh", "STANDARD"): "0.115",
    ("petrol_per_litre", "STANDARD"): "1.85",
    ("diesel_per_litre", "STANDARD"): "1.75",
    ("retail_per_kwh", "STANDARD"): "0.37",
    ("feedin_per_kwh", "STANDARD"): "0.0778",
    ("public_charge_per_kwh", "STANDARD"): "0.45",
}


def _sql() -> tuple[str, str]:
    return (
        MIGRATION.read_text(encoding="utf-8"),
        SEED.read_text(encoding="utf-8"),
    )


def _table_body(migration: str, table: str) -> str:
    match = re.search(
        rf"create table if not exists public\.{table}\s*\((.*?)\n\);",
        migration,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert match is not None, f"missing table {table}"
    return match.group(1)


def test_all_eight_tables_and_columns_exist() -> None:
    migration, _ = _sql()

    for table, expected_columns in EXPECTED_TABLE_COLUMNS.items():
        body = _table_body(migration, table)
        for column in expected_columns:
            assert re.search(rf"^\s*{column}\s", body, flags=re.MULTILINE)

    price_body = _table_body(migration, "price_catalog")
    assert "primary key (component, tier, valid_from)" in price_body.lower()
    proposal_body = _table_body(migration, "proposal")
    assert "references public.advise_run(id)" in proposal_body.lower()


def test_seed_contains_exact_price_catalog_rows_with_sources() -> None:
    _, seed = _sql()
    row_pattern = re.compile(
        r"\('([^']+)', '([^']+)', '[^']+', ([0-9.]+), '([^']+)', date '([^']+)'\)"
    )
    rows = row_pattern.findall(seed)

    assert len(rows) == 12
    actual = {(component, tier): price for component, tier, price, _, _ in rows}
    assert actual == EXPECTED_PRICES
    assert all(source.strip() for _, _, _, source, _ in rows)
    assert all(valid_from == "2026-06-20" for _, _, _, _, valid_from in rows)


def test_demo_reference_rows_are_complete_and_offline() -> None:
    _, seed = _sql()

    assert (
        "('10115', 52.5323, 13.3846, 980.0, 0.37, 0.0, 'DE-4', 47)"
        in seed
    )
    assert (
        "('80331', 48.1372, 11.5756, 980.0, 0.37, 0.0, 'DE-5', 63)"
        in seed
    )
    assert "http://" not in seed
    assert "https://" not in seed


def test_migration_and_seed_are_idempotent() -> None:
    migration, seed = _sql()

    assert migration.lower().count("create table if not exists") == 8
    assert seed.lower().count("on conflict") == 4
    assert "on conflict (component, tier, valid_from)" in seed.lower()


def test_no_seeded_prices_are_hard_coded_in_engine_or_adapters() -> None:
    guarded_paths = [
        ROOT / "apps/api/src/app/domain/savings",
        ROOT / "apps/api/src/app/adapters",
    ]
    guarded_text = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in guarded_paths
        for path in directory.rglob("*.py")
    )

    for literal in EXPECTED_PRICES.values():
        assert literal not in guarded_text


def test_supabase_client_is_configured_without_network_access() -> None:
    settings = Settings(
        supabase_url="https://demo.supabase.co/",
        supabase_service_role_key="server-only-test-key",
    )

    with get_supabase_client(settings) as client:
        assert str(client.base_url) == "https://demo.supabase.co/rest/v1/"
        assert client.headers["apikey"] == "server-only-test-key"
        assert client.headers["authorization"] == "Bearer server-only-test-key"


def test_supabase_client_requires_server_side_credentials() -> None:
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        get_supabase_client(Settings())
