"""Dynamic-tariff adapter — SMARD/aWATTar price spread (F14).

Owner: Zhou (backend)
Feature ID: F14 (dynamic tariff adapter)

Interface: get_dynamic_spread() -> float  (EUR/kWh net spread)

Live SMARD/aWATTar call is gated behind DYNPRICE_LIVE=true (env toggle).
Default / MVP returns the seeded €0.12/kWh net spread offline (AC5/AC6).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.domain.models import Assumption

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Seeded representative net spread (§7.1 / §10) — SMARD/EPEX day-ahead DE
FALLBACK_SPREAD_EUR_PER_KWH: float = 0.12

# Primary: SMARD (Bundesnetzagentur); alternate: aWATTar (EPEX day-ahead)
_SMARD_BASE = "https://www.smard.de/app/chart_data"
_AWATTAR_URL = "https://api.awattar.de/v1/marketdata"

# Default number of hours for mean(top-N) / mean(bottom-N) spread formula
_DEFAULT_N_HOURS: int = 6


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class DynamicTariffProvider:
    """Day-ahead electricity price spread for battery and EV arbitrage.

    Parameters
    ----------
    live:
        If True, fetches from SMARD (primary) or aWATTar (alt).
        Default False — MVP / demo mode returns the seeded €0.12 spread
        without any network call (AC6 toggle off = offline).
    n_hours:
        Number of peak/off-peak hours for the spread formula (default 6).
    timeout:
        HTTP timeout for live calls.
    """

    def __init__(
        self,
        live: bool = False,
        n_hours: int = _DEFAULT_N_HOURS,
        timeout: float = 10.0,
    ) -> None:
        self._live = live
        self._n_hours = n_hours
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_dynamic_spread(self) -> tuple[float, list[Assumption]]:
        """Return (spread_eur_per_kwh, assumptions).

        On fallback the assumption is labelled so callers can surface it
        in the response (§3.4 / §7.1).  The spread is always shown on its
        own 'widest-band' line, never blended into the certain buckets (AC7).
        """
        if self._live:
            return self._live_fetch()
        return self._seeded_fallback()

    def spread(self, **kwargs: Any) -> float:
        """Return net spread EUR/kWh (legacy API, no assumptions list)."""
        value, _ = self.get_dynamic_spread()
        return value

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _live_fetch(self) -> tuple[float, list[Assumption]]:
        """Attempt SMARD, then aWATTar, then seeded fallback."""
        smard_result = self._try_smard()
        if smard_result is not None:
            return smard_result, []
        awattar_result = self._try_awattar()
        if awattar_result is not None:
            return awattar_result, []
        return self._seeded_fallback()

    def _try_smard(self) -> float | None:
        """Fetch day-ahead prices from SMARD (primary source)."""
        # SMARD hourly index; filter 4169 = day-ahead DE (§7.1)
        url = f"{_SMARD_BASE}/4169/4169/index_hour.json"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
            if resp.status_code == 200:
                payload = resp.json()
                return self._compute_spread_from_smard(payload)
        except Exception:
            logger.debug("SMARD fetch failed; trying aWATTar", exc_info=True)
        return None

    def _try_awattar(self) -> float | None:
        """Fetch day-ahead prices from aWATTar (alternate source)."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(_AWATTAR_URL)
            if resp.status_code == 200:
                payload = resp.json()
                return self._compute_spread_from_awattar(payload)
        except Exception:
            logger.debug("aWATTar fetch failed; using seeded spread", exc_info=True)
        return None

    def _compute_spread(self, prices_eur_kwh: list[float]) -> float:
        """Compute mean(top-N) − mean(bottom-N) (AC2 spread formula)."""
        if not prices_eur_kwh:
            return FALLBACK_SPREAD_EUR_PER_KWH
        n = min(self._n_hours, len(prices_eur_kwh))
        sorted_prices = sorted(prices_eur_kwh)
        bottom_n = sorted_prices[:n]
        top_n = sorted_prices[-n:]
        return sum(top_n) / n - sum(bottom_n) / n

    def _compute_spread_from_smard(self, payload: dict[str, Any]) -> float | None:
        """Extract hourly prices from SMARD index payload and compute spread."""
        try:
            # SMARD returns { "timestamps": [...], "series": [[ts, price_eur_mwh], ...] }
            series: list[list[float]] = payload.get("series", [])
            if not series:
                return None
            # Convert MWh → kWh (divide by 1000)
            prices = [pt[1] / 1000.0 for pt in series if pt[1] is not None]
            if not prices:
                return None
            return self._compute_spread(prices)
        except (KeyError, TypeError, IndexError):
            logger.debug("SMARD payload parse error; falling back", exc_info=True)
            return None

    def _compute_spread_from_awattar(self, payload: dict[str, Any]) -> float | None:
        """Extract hourly prices from aWATTar payload and compute spread."""
        try:
            data: list[dict[str, Any]] = payload.get("data", [])
            if not data:
                return None
            # aWATTar: marketprice is in EUR/MWh
            prices = [float(item["marketprice"]) / 1000.0 for item in data if "marketprice" in item]
            if not prices:
                return None
            return self._compute_spread(prices)
        except (KeyError, TypeError):
            logger.debug("aWATTar payload parse error; falling back", exc_info=True)
            return None

    @staticmethod
    def _seeded_fallback() -> tuple[float, list[Assumption]]:
        """Return the seeded €0.12/kWh spread with a labelled assumption (AC5)."""
        assumption = Assumption(
            field="dynamic_spread_eur_kwh",
            value=f"€{FALLBACK_SPREAD_EUR_PER_KWH}/kWh (seeded fallback)",
            source="Representative SMARD/EPEX day-ahead DE net spread (§7.1 / §10)",
            editable=True,
        )
        return FALLBACK_SPREAD_EUR_PER_KWH, [assumption]