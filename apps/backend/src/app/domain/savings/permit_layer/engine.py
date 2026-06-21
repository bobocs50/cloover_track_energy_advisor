"""Permit engine — runs all 12 checks concurrently, caches results, generates LLM summary."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from app.domain.savings.permit_layer.checks import (
    PermitCheck,
    check_battery_install,
    check_battery_mastr,
    check_bplan,
    check_denkmal_heatpump,
    check_denkmal_solar,
    check_ev_parking,
    check_ev_weg,
    check_hp_geg,
    check_hp_noise,
    check_mastr,
    check_solar_lbo,
    plz_to_bundesland,
)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


@dataclass
class PermitMatrix:
    address: str
    lat: float
    lng: float
    plz: str
    bundesland: str
    checks: list[PermitCheck]
    any_fatal: bool
    solar_blocked: bool
    heatpump_blocked: bool
    ev_charger_blocked: bool
    neighbour_count: int
    summary_de: str


def _address_hash(address: str) -> str:
    return hashlib.sha256(address.lower().strip().encode()).hexdigest()[:32]


def _load_cache(address: str, supabase_url: str, supabase_key: str) -> PermitMatrix | None:
    if not supabase_url or not supabase_key:
        return None
    try:
        h = _address_hash(address)
        resp = httpx.get(
            f"{supabase_url.rstrip('/')}/rest/v1/permit_cache",
            params={"address_hash": f"eq.{h}", "select": "result_json,fetched_at"},
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            timeout=5,
        )
        rows = resp.json()
        if not rows:
            return None
        row = rows[0]
        # TTL: 7 days
        from datetime import datetime, timezone
        fetched = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - fetched).days
        if age_days > 7:
            return None
        data = row["result_json"]
        checks = [PermitCheck(**c) for c in data["checks"]]
        return PermitMatrix(
            address=data["address"], lat=data["lat"], lng=data["lng"],
            plz=data["plz"], bundesland=data["bundesland"],
            checks=checks, any_fatal=data["any_fatal"],
            solar_blocked=data["solar_blocked"], heatpump_blocked=data["heatpump_blocked"],
            ev_charger_blocked=data["ev_charger_blocked"],
            neighbour_count=data["neighbour_count"], summary_de=data["summary_de"],
        )
    except Exception:
        return None


def _save_cache(matrix: PermitMatrix, supabase_url: str, supabase_key: str) -> None:
    if not supabase_url or not supabase_key:
        return
    try:
        h = _address_hash(matrix.address)
        httpx.post(
            f"{supabase_url.rstrip('/')}/rest/v1/permit_cache",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            json={"address_hash": h, "address": matrix.address, "result_json": asdict(matrix)},
            timeout=5,
        )
    except Exception:
        pass  # cache write failure is non-fatal


def _llm_summary(checks: list[PermitCheck], address: str, anthropic_api_key: str) -> str:
    if not anthropic_api_key:
        return ""
    results_text = "\n".join(
        f"- {c.check_name} ({c.product}): {c.status} — {c.label}"
        for c in checks
    )
    prompt = (
        f"Write a short, factual paragraph in English (2–3 sentences) summarising the "
        f"permit situation for the following address: {address}\n\n"
        f"Check results:\n{results_text}\n\n"
        "Style: professional, clear, no marketing speak. State specifically what is permitted, "
        "what needs to be checked, and what (if anything) is not possible."
    )
    try:
        resp = httpx.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key": anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()
    except Exception:
        return ""


def run_permit_checks(
    address: str,
    plz: str,
    lat: float,
    lng: float,
    intake: dict[str, Any],
    *,
    tavily_api_key: str = "",
    anthropic_api_key: str = "",
    supabase_url: str = "",
    supabase_key: str = "",
) -> PermitMatrix:
    """Run all 12 permit checks concurrently and return a PermitMatrix.

    Checks Supabase cache first (TTL 7 days). Falls back to live API calls.
    """
    cached = _load_cache(address, supabase_url, supabase_key)
    if cached is not None:
        return cached

    bundesland = plz_to_bundesland(plz)

    # e.g. "Am Nahholz 55, 74722 Buchen" → "Buchen"
    city = address.split(",")[-1].strip().split()[-1] if "," in address else plz

    building_year: int = int(intake.get("building_year", 1985))
    fuel_type: str = str(intake.get("fuel_type", "GAS"))
    has_private_parking: bool = bool(intake.get("has_private_parking", False))

    # Define all check tasks
    def _safe(fn: Any, *args: Any, **kwargs: Any) -> list[PermitCheck] | PermitCheck:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            from app.domain.savings.permit_layer.checks import _make_check
            fn_name = getattr(fn, "__name__", "unknown")
            return _make_check(
                fn_name, "unknown", fn_name, "warn",
                "Check unavailable",
                f"Could not complete check ({exc}). Verify manually.",
                "Error",
            )

    tasks = {
        "solar_lbo": lambda: _safe(check_solar_lbo, bundesland),
        "solar_denkmal": lambda: _safe(check_denkmal_solar, lat, lng, bundesland),
        "hp_denkmal": lambda: _safe(check_denkmal_heatpump, lat, lng, bundesland),
        "bplan": lambda: _safe(check_bplan, plz, city, tavily_api_key, anthropic_api_key),
        "mastr": lambda: _safe(check_mastr, plz, supabase_url, supabase_key, tavily_api_key),
        "ev_parking": lambda: _safe(check_ev_parking, lat, lng, has_private_parking),
        "ev_weg": lambda: _safe(check_ev_weg, lat, lng),
        "hp_geg": lambda: _safe(check_hp_geg, building_year, fuel_type),
        "hp_noise": lambda: _safe(check_hp_noise, lat, lng),
        "battery_install": lambda: _safe(check_battery_install),
        "battery_mastr": lambda: _safe(check_battery_mastr),
    }

    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()

    # Flatten all checks into a list (bplan returns 2 checks)
    checks: list[PermitCheck] = []
    for key in ["solar_lbo", "solar_denkmal", "hp_denkmal", "bplan", "mastr",
                "ev_parking", "ev_weg", "hp_geg", "hp_noise", "battery_install", "battery_mastr"]:
        r = results.get(key)
        if isinstance(r, list):
            checks.extend(r)
        elif isinstance(r, PermitCheck):
            checks.append(r)

    solar_blocked = any(
        c.status == "fail" and c.product == "solar" for c in checks
    )
    heatpump_blocked = any(
        c.status == "fail" and c.product == "heatpump" for c in checks
    )
    ev_charger_blocked = any(
        c.status == "fail" and c.product == "ev_charger" for c in checks
    )
    any_fatal = solar_blocked or heatpump_blocked or ev_charger_blocked

    mastr_check = next((c for c in checks if c.id == "solar_mastr"), None)
    neighbour_count = 0
    if mastr_check and mastr_check.status == "pass":
        try:
            neighbour_count = int(mastr_check.label.split()[0])
        except Exception:
            pass

    summary_de = _llm_summary(checks, address, anthropic_api_key)

    matrix = PermitMatrix(
        address=address, lat=lat, lng=lng, plz=plz, bundesland=bundesland,
        checks=checks, any_fatal=any_fatal,
        solar_blocked=solar_blocked, heatpump_blocked=heatpump_blocked,
        ev_charger_blocked=ev_charger_blocked,
        neighbour_count=neighbour_count, summary_de=summary_de,
    )

    _save_cache(matrix, supabase_url, supabase_key)
    return matrix
