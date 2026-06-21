"""Live energy price fetcher — Elecz (electricity spot, no API key).

https://elecz.com/signal/spot?zone=DE
Returns EPEX SPOT in EUR/MWh, updated hourly.
Retail estimate = spot_EUR_kWh + RETAIL_OVERHEAD_EUR_KWH.
Returns None on any failure; caller falls back to seed value.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# German household markup on top of EPEX SPOT:
#   Netzentgelt ~0.09 + StromSteuer 0.021 + Konzessionsabgabe 0.018
#   + VAT 19 % + retailer margin ≈ 0.21 EUR/kWh
#   Source: BNetzA Monitoringbericht 2025
RETAIL_OVERHEAD_EUR_KWH: float = 0.21

_URL = "https://elecz.com/signal/spot"


def fetch_electricity_retail(timeout: float = 8.0) -> float | None:
    """EUR/kWh retail estimate, or None if the API is unreachable."""
    try:
        resp = httpx.get(_URL, params={"zone": "DE"}, timeout=timeout)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        raw = (
            data.get("price")
            or data.get("current_price")
            or (data.get("data") or {}).get("price")
        )
        if raw is None:
            logger.warning("price_fetcher: no price in Elecz response: %s", data)
            return None

        spot = float(raw) / 1000.0          # EUR/MWh → EUR/kWh
        retail = round(spot + RETAIL_OVERHEAD_EUR_KWH, 4)

        if not (0.15 <= retail <= 0.80):
            logger.warning("price_fetcher: retail %.4f out of plausible range", retail)
            return None

        logger.info("price_fetcher: electricity %.4f EUR/kWh (spot %.4f + overhead %.2f)",
                    retail, spot, RETAIL_OVERHEAD_EUR_KWH)
        return retail

    except Exception as exc:
        logger.warning("price_fetcher: Elecz unavailable — %s", exc)
        return None
