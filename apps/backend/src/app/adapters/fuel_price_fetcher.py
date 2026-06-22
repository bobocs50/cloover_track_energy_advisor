"""Live fuel price fetcher — Tankerkönig (petrol / diesel, requires API key).

https://creativecommons.tankerkoenig.de/json/list.php
Returns nearby station prices; we take the median of open stations within 10 km.
Returns (None, None) on any failure; caller falls back to seed values.
"""
from __future__ import annotations

import logging
import statistics
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_URL = "https://creativecommons.tankerkoenig.de/json/list.php"
_RADIUS_KM = 10
_MIN_EUR_L = 1.20
_MAX_EUR_L = 2.50


def fetch_fuel_prices(
    lat: float,
    lon: float,
    api_key: str,
    timeout: float = 8.0,
) -> tuple[float | None, float | None]:
    """Return (petrol_eur_per_litre, diesel_eur_per_litre) or (None, None)."""
    if not api_key:
        logger.debug("fuel_price_fetcher: no API key — skipping live fetch")
        return None, None
    try:
        resp = httpx.get(
            _URL,
            params={"lat": lat, "lng": lon, "rad": _RADIUS_KM, "sort": "dist", "type": "all", "apikey": api_key},
            timeout=timeout,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        if not data.get("ok"):
            logger.warning("fuel_price_fetcher: API returned ok=false: %s", data.get("message"))
            return None, None

        stations: list[dict[str, Any]] = data.get("stations") or []
        open_stations = [s for s in stations if s.get("isOpen")]

        petrol = _median_price(open_stations, "e5")
        diesel = _median_price(open_stations, "diesel")

        logger.info(
            "fuel_price_fetcher: petrol=%s diesel=%s EUR/L (%d open stations within %d km)",
            f"{petrol:.3f}" if petrol else "n/a",
            f"{diesel:.3f}" if diesel else "n/a",
            len(open_stations),
            _RADIUS_KM,
        )
        return petrol, diesel

    except Exception as exc:
        logger.warning("fuel_price_fetcher: Tankerkönig unavailable — %s", exc)
        return None, None


def _median_price(stations: list[dict[str, Any]], field: str) -> float | None:
    prices = []
    for s in stations:
        raw = s.get(field)
        if raw is False or raw is None:
            continue
        try:
            v = float(raw)
        except (TypeError, ValueError):
            continue
        if _MIN_EUR_L <= v <= _MAX_EUR_L:
            prices.append(v)
    if not prices:
        return None
    return round(statistics.median(prices), 3)
