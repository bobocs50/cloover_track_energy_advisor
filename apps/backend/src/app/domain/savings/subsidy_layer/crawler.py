"""Subsidy crawler — Tavily fetch → OpenAI extract → gate → Supabase upsert.

Runs on a schedule (jobs/refresh_subsidies.py) or via POST /advisor/subsidies/refresh.
Writes promoted rows to subsidy_catalog (engine reads these).
Writes suspicious rows to subsidy_catalog_staging (quarantine — never touches the number).

Mirrors permit_layer's pattern: sync httpx, ThreadPoolExecutor fan-out, graceful
degradation (missing keys → no-op, not a crash).
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_OPENAI_MODEL = "gpt-4o-mini"

# Federal sources to refresh weekly.
# Each entry: name matches subsidy_catalog.programme; components lists which
# catalog rows this source covers (one Tavily call can produce multiple rows).
SOURCES: list[dict[str, Any]] = [
    {
        "name": "kfw_458_heat_pump",
        "query": "KfW 458 Heizungsförderung Fördersatz Grundförderung Geschwindigkeitsbonus 2026",
        "url": "https://www.kfw.de/inlandsfoerderung/Privatpersonen/Bestehende-Immobilie/F%C3%B6rderprodukte/Heizungsf%C3%B6rderung-f%C3%BCr-Privatpersonen-Wohngeb%C3%A4ude-(458)/",
        "components": ["heat_pump_a", "heat_pump_b"],
        "parser_hint": (
            "Extract KfW 458 subsidy rates for heat pumps. Look for:\n"
            "- 'Grundförderung' or 'base rate': applies to ALL heat pump replacements\n"
            "- 'Klima-Geschwindigkeitsbonus' or 'speed bonus': only for replacing fossil heating (oil/gas)\n"
            "- 'cap' or 'Höchstbetrag': the maximum grant in EUR\n"
            "Return JSON array of objects matching the schema."
        ),
    },
    {
        "name": "vat_pv_battery",
        "query": "§12 UStG Solaranlage Photovoltaik Batteriespeicher Umsatzsteuer 0 Prozent 2026",
        "url": "https://www.gesetze-im-internet.de/ustg_1980/__12.html",
        "components": ["pv", "battery"],
        "parser_hint": (
            "Confirm the 0% VAT rate under §12(3) UStG for PV systems and battery storage. "
            "rate should be 0.00 (it is a VAT exemption, not a cash grant). "
            "Return one row per component (pv, battery)."
        ),
    },
    {
        "name": "bafa_ev_umweltbonus",
        "query": "BAFA Umweltbonus Elektromobilität Förderung 2026 status eingestellt",
        "url": "https://www.bafa.de/DE/Energie/Energieeffizienz/Elektromobilitaet/elektromobilitaet_node.html",
        "components": ["ev_charger"],
        "parser_hint": (
            "Check if the BAFA Umweltbonus for electric vehicles is still active. "
            "It ended on 17 December 2023. If still ended, return rate=0.0, cap_eur=0, "
            "valid_until='2023-12-17'. If somehow reinstated, return the new rate."
        ),
    },
]

# Extraction JSON schema sent to OpenAI (response_format = json_schema).
_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "programme": {"type": "string"},
                    "component": {
                        "type": "string",
                        "enum": ["heat_pump_a", "heat_pump_b", "pv", "battery", "ev_charger"],
                    },
                    "rate": {"type": "number"},
                    "cap_eur": {"type": ["number", "null"]},
                    "valid_until": {"type": ["string", "null"]},
                    "notes": {"type": "string"},
                },
                "required": ["programme", "component", "rate"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rows"],
    "additionalProperties": False,
}


@dataclass
class CrawlResult:
    promoted: int = 0
    quarantined: int = 0
    errors: int = 0
    crawled_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "promoted": self.promoted,
            "quarantined": self.quarantined,
            "errors": self.errors,
            "crawled_at": self.crawled_at,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tavily_fetch(query: str, tavily_key: str) -> str:
    """Call Tavily search and return the concatenated result content."""
    resp = httpx.post(
        _TAVILY_URL,
        json={
            "api_key": tavily_key,
            "query": query,
            "max_results": 5,
            "include_raw_content": False,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    parts: list[str] = []
    for r in data.get("results", []):
        if r.get("content"):
            parts.append(f"URL: {r.get('url', '')}\n{r['content']}")
    return "\n\n---\n\n".join(parts)[:6000]  # trim to avoid token overflow


def _openai_extract(
    raw_text: str,
    source: dict[str, Any],
    openai_key: str,
) -> list[dict[str, Any]]:
    """Call OpenAI with structured output schema to extract subsidy rows from raw text."""
    system_prompt = (
        "You are a German subsidy data extractor. Given raw text from official German "
        "government pages, extract subsidy rates as structured JSON. "
        "Only extract numbers explicitly stated in the text — never invent or assume rates. "
        "Rates are fractions (0.30 = 30%, 0.20 = 20%, 0.00 = 0%). "
        "programme names must match the provided source name exactly."
    )
    user_prompt = (
        f"Source name: {source['name']}\n"
        f"Components to extract: {', '.join(source['components'])}\n"
        f"Extraction hint: {source['parser_hint']}\n\n"
        f"Raw text from official pages:\n{raw_text}\n\n"
        "Return a JSON object with a 'rows' array matching the schema."
    )
    resp = httpx.post(
        _OPENAI_URL,
        headers={
            "Authorization": f"Bearer {openai_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "subsidy_rows",
                    "schema": _EXTRACT_SCHEMA,
                    "strict": True,
                },
            },
            "max_tokens": 800,
            "temperature": 0,
        },
        timeout=30,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content).get("rows", [])


def _fetch_live_row(
    programme: str,
    component: str,
    supabase_url: str,
    supabase_key: str,
) -> dict[str, Any] | None:
    """Read the current live row for this (programme, component) from Supabase."""
    try:
        resp = httpx.get(
            f"{supabase_url.rstrip('/')}/rest/v1/subsidy_catalog",
            params={
                "select": "rate,cap_eur,valid_until",
                "programme": f"eq.{programme}",
                "component": f"eq.{component}",
                "order": "valid_from.desc",
                "limit": "1",
            },
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            timeout=5,
        )
        rows = resp.json()
        return rows[0] if rows else None
    except Exception:
        return None


def _validate_gate(
    proposed: dict[str, Any],
    live_row: dict[str, Any] | None,
    source_url: str,
) -> tuple[bool, str]:
    """Sanity check a proposed row before promotion.

    Returns (passes: bool, note: str).
    Rules:
      - rate: 0 ≤ rate ≤ 1
      - source_url: present and starts with https://
      - rate_jump: if live row exists, |proposed.rate - live.rate| ≤ 0.25
    """
    rate = proposed.get("rate")
    if rate is None or not (0 <= rate <= 1):
        return False, f"rate out of bounds: {rate}"
    if not source_url or not source_url.startswith("https://"):
        return False, f"invalid source_url: {source_url!r}"
    if live_row is not None:
        live_rate = float(live_row.get("rate", 0))
        jump = abs(rate - live_rate)
        if jump > 0.25 + 1e-9:  # tolerance ≤ 0.25; epsilon avoids float precision issues
            return False, f"rate jumped too far: {live_rate} → {rate} (Δ{jump:.2f} > 0.25)"
    return True, "ok"


def _upsert_catalog(
    row: dict[str, Any],
    source_url: str,
    promote: bool,
    raw_excerpt: str,
    diff_note: str,
    supabase_url: str,
    supabase_key: str,
) -> None:
    """Write to subsidy_catalog (promote=True) or subsidy_catalog_staging (promote=False)."""
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    today = date.today().isoformat()
    if promote:
        payload: dict[str, Any] = {
            "programme": row["programme"],
            "component": row["component"],
            "rate": row["rate"],
            "cap_eur": row.get("cap_eur"),
            "unit": "fraction_of_capex",
            "source_url": source_url,
            "valid_from": today,
            "valid_until": row.get("valid_until"),
            "notes": row.get("notes", ""),
        }
        httpx.post(
            f"{supabase_url.rstrip('/')}/rest/v1/subsidy_catalog",
            headers=headers,
            json=payload,
            timeout=5,
        ).raise_for_status()
    else:
        payload = {
            "programme": row["programme"],
            "component": row["component"],
            "rate": row.get("rate"),
            "cap_eur": row.get("cap_eur"),
            "source_url": source_url,
            "raw_excerpt": raw_excerpt[:1000],
            "diff_note": diff_note,
            "status": "proposed",
        }
        httpx.post(
            f"{supabase_url.rstrip('/')}/rest/v1/subsidy_catalog_staging",
            headers={**headers, "Prefer": "return=minimal"},
            json=payload,
            timeout=5,
        ).raise_for_status()


def _process_source(
    source: dict[str, Any],
    tavily_key: str,
    openai_key: str,
    supabase_url: str,
    supabase_key: str,
) -> dict[str, int]:
    """Fetch + extract + gate + upsert one source. Returns {promoted, quarantined, errors}."""
    counts = {"promoted": 0, "quarantined": 0, "errors": 0}
    try:
        raw_text = _tavily_fetch(source["query"], tavily_key)
    except Exception as exc:
        logger.warning("Tavily fetch failed for %s: %s", source["name"], exc)
        counts["errors"] += 1
        return counts

    try:
        rows = _openai_extract(raw_text, source, openai_key)
    except Exception as exc:
        logger.warning("OpenAI extract failed for %s: %s", source["name"], exc)
        counts["errors"] += 1
        return counts

    for row in rows:
        if row.get("component") not in source["components"]:
            continue  # OpenAI returned a component we didn't ask for — skip
        live_row = _fetch_live_row(
            row["programme"], row["component"], supabase_url, supabase_key
        )
        passes, note = _validate_gate(row, live_row, source["url"])
        try:
            _upsert_catalog(
                row=row,
                source_url=source["url"],
                promote=passes,
                raw_excerpt=raw_text[:500],
                diff_note=note if not passes else "",
                supabase_url=supabase_url,
                supabase_key=supabase_key,
            )
            if passes:
                counts["promoted"] += 1
            else:
                logger.warning("Quarantined %s/%s: %s", row["programme"], row["component"], note)
                counts["quarantined"] += 1
        except Exception as exc:
            logger.warning("Upsert failed for %s/%s: %s", row.get("programme"), row.get("component"), exc)
            counts["errors"] += 1

    return counts


def refresh_federal(
    *,
    tavily_key: str = "",
    openai_key: str = "",
    supabase_url: str = "",
    supabase_key: str = "",
) -> CrawlResult:
    """Refresh all federal subsidy sources concurrently.

    Missing keys → returns a no-op CrawlResult (permit_layer pattern).
    Each source is processed in a ThreadPoolExecutor; failures are logged, not raised.
    """
    result = CrawlResult(crawled_at=_now_iso())

    if not tavily_key or not openai_key:
        logger.warning("Subsidy crawler: missing Tavily or OpenAI key — skipping refresh")
        result.errors = len(SOURCES)
        return result

    if not supabase_url or not supabase_key:
        logger.warning("Subsidy crawler: missing Supabase credentials — skipping refresh")
        result.errors = len(SOURCES)
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                _process_source,
                source,
                tavily_key,
                openai_key,
                supabase_url,
                supabase_key,
            ): source["name"]
            for source in SOURCES
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                counts = future.result()
                result.promoted += counts["promoted"]
                result.quarantined += counts["quarantined"]
                result.errors += counts["errors"]
            except Exception as exc:
                logger.error("Source %s failed: %s", name, exc)
                result.errors += 1

    return result
