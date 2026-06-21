"""PVGIS irradiance provider (F13).

Owner: Zhou (backend)
Feature ID: F13 (PVGIS adapter)

Interface: get_specific_yield(lat, lon) -> float

Live PVGIS call is gated behind PVGIS_LIVE=true (env toggle, §13.2/§16).
Default / MVP returns constant 980.0 kWh/kWp/yr offline fallback (AC5/AC6).
All network calls are guarded; malformed payloads fall back gracefully (AC7).
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

# Deterministic offline fallback (kWh per kWp per year) — PVGIS DE average §10
FALLBACK_YIELD_KWH_PER_KWP: float = 980.0

# PVGIS PVcalc endpoint (EU JRC, keyless)
_PVGIS_BASE = "https://re.jrc.ec.europa.eu/api/v5_2"

# Default tilt / azimuth (§5.1)
DEFAULT_TILT: float = 35.0
DEFAULT_AZIMUTH: float = 0.0
DEFAULT_LOSS: float = 14.0


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class PVGISProvider:
    """Annual specific PV yield from PVGIS (EU JRC) with 980 fallback.

    Parameters
    ----------
    live:
        If True and ``httpx`` is available, issues a real PVGIS call.
        Default False — MVP / demo mode returns the 980 fallback without
        any network call (AC6 toggle off = offline).
    timeout:
        HTTP timeout in seconds for the live call.
    """

    def __init__(self, live: bool = False, timeout: float = 10.0) -> None:
        self._live = live
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_specific_yield(
        self,
        lat: float,
        lon: float,
        total_kwp: float = 1.0,
        tilt: float = DEFAULT_TILT,
        azimuth: float = DEFAULT_AZIMUTH,
    ) -> tuple[float, list[Assumption]]:
        """Return (specific_yield_kwh_per_kwp, assumptions).

        specific_yield_kwh_per_kwp is the annual yield per installed kWp.
        On fallback the assumption is labelled so callers can surface it.
        """
        if self._live:
            return self._live_fetch(
                lat=lat, lon=lon, total_kwp=total_kwp, tilt=tilt, azimuth=azimuth
            )
        return self._offline_fallback(lat=lat, lon=lon, total_kwp=total_kwp)

    def annual_yield(self, lat: float, lon: float, **kwargs: Any) -> float:
        """Return specific yield kWh/kWp/yr (legacy API, no assumptions list)."""
        total_kwp = float(kwargs.get("total_kwp", 1.0))
        tilt = float(kwargs.get("tilt", DEFAULT_TILT))
        azimuth = float(kwargs.get("azimuth", DEFAULT_AZIMUTH))
        yield_kwh_per_kwp, _ = self.get_specific_yield(
            lat=lat, lon=lon, total_kwp=total_kwp, tilt=tilt, azimuth=azimuth
        )
        return yield_kwh_per_kwp

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _live_fetch(
        self,
        lat: float,
        lon: float,
        total_kwp: float,
        tilt: float,
        azimuth: float,
    ) -> tuple[float, list[Assumption]]:
        """Issue a real PVcalc GET request (AC1 URL contract)."""
        url = f"{_PVGIS_BASE}/PVcalc"
        params: dict[str, str | float] = {
            "lat": lat,
            "lon": lon,
            "peakpower": total_kwp,
            "loss": DEFAULT_LOSS,
            "mountingplace": "building",
            "angle": tilt,
            "aspect": azimuth,
            "outputformat": "json",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, params=params)
            if resp.status_code == 200:
                return self._parse_response(resp.json(), total_kwp=total_kwp)
        except Exception:
            logger.debug("PVGIS live fetch failed; falling back to 980", exc_info=True)
        return self._offline_fallback(lat=lat, lon=lon, total_kwp=total_kwp)

    def _parse_response(
        self, payload: dict[str, Any], total_kwp: float
    ) -> tuple[float, list[Assumption]]:
        """Extract E_y from the PVcalc JSON (AC2 / AC7 defensive parse)."""
        try:
            e_y: float = float(payload["outputs"]["totals"]["fixed"]["E_y"])
            # E_y is total annual yield (kWh); specific yield = E_y / kwp
            specific_yield = e_y / total_kwp if total_kwp > 0 else e_y
            return specific_yield, []
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "PVGIS response missing outputs.totals.fixed.E_y — using 980 fallback (AC7)"
            )
        return self._offline_fallback(lat=0.0, lon=0.0, total_kwp=total_kwp)

    @staticmethod
    def _offline_fallback(
        lat: float, lon: float, total_kwp: float
    ) -> tuple[float, list[Assumption]]:
        """Return 980 fallback with a labelled assumption (AC5)."""
        assumption = Assumption(
            field="specific_yield_kwh_per_kwp",
            value=f"{FALLBACK_YIELD_KWH_PER_KWP} kWh/kWp",
            source="PVGIS fallback (offline / toggle off)",
            editable=True,
        )
        return FALLBACK_YIELD_KWH_PER_KWP, [assumption]