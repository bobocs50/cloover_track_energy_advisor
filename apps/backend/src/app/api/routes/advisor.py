"""Advisor routes — wired (F17).

Owner: Zhou (backend)
Feature ID: F17 (api endpoints) — contract from F02

Implements POST /api/v1/advisor/recommend and POST /api/v1/advisor/site-check
against the frozen F02 contract.  No new schema fields are added here.

?fixture=<id>  → returns the golden payload from apps/api/fixtures/<id>.json
                 with NO engine / LLM / DB call (AC4 / §1).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.domain.models import (
    Household,
    Recommendation,
    SiteCheckRequest,
    SiteCheckResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/advisor", tags=["advisor"])

# Fixtures directory: Path(__file__) is .../src/app/api/routes/advisor.py
# parents[4] = apps/api  →  fixtures/ lives at apps/api/fixtures/
_FIXTURES_DIR = Path(__file__).parents[4] / "fixtures"


# ---------------------------------------------------------------------------
# /recommend
# ---------------------------------------------------------------------------


@router.post("/recommend", response_model=Recommendation)
def recommend(
    body: Household,
    fixture: str | None = None,
) -> Recommendation:
    """Run the savings ladder and return ranked upgrade paths.

    alternatives[] is the four-rung cumulative ladder (☀️→🔋→♨️→🚗).
    Per-layer "+€X/mo" = consecutive differences of alternatives[].monthly_saving_eur.
    Use ?fixture=<id> (e.g. "demo-detached") to return a frozen golden payload (F24).
    """
    # ── ?fixture short-circuit (AC4 — no engine/LLM/DB call) ───────────────
    if fixture:
        return _load_fixture(fixture, "recommend")

    # ── Live pipeline ────────────────────────────────────────────────────────
    from app.services.recommendation import RecommendationService

    svc = RecommendationService()
    try:
        return svc.run(body)
    except Exception as exc:
        # Any failure — degrade gracefully (AC7); the ?fixture path stays available.
        logger.error("RecommendationService.run failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Recommendation failed: {exc!s}",
        ) from exc


# ---------------------------------------------------------------------------
# /recommend/stream  (live activity SSE)
# ---------------------------------------------------------------------------


@router.post("/recommend/stream")
def recommend_stream(
    body: Household,
    fixture: str | None = None,
) -> StreamingResponse:
    """Same pipeline as /recommend, streamed as SSE `PipelineEvent`s (live activity).

    Emits one event per real step (resolve → ladder → subsidy → LLM → persist); the
    terminal `run_completed` event carries the full Recommendation in `payload.recommendation`.
    Read it with a fetch streaming reader (the body is a POST), not `EventSource`.
    Use ?fixture=<id> to stream a canned sequence off a golden payload.
    """
    from app.services.run_stream import stream_recommendation

    return StreamingResponse(
        stream_recommendation(body, fixture=fixture),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# /site-check
# ---------------------------------------------------------------------------


@router.post("/site-check", response_model=SiteCheckResponse)
def site_check(
    body: SiteCheckRequest,
    fixture: str | None = None,
) -> SiteCheckResponse:
    """Validate an address / roof for feasibility and return energy context.

    Called before /recommend to display the green/amber feasibility panel (§4, §14.2).
    Use ?fixture=<id> to return a canned payload.
    """
    # ── ?fixture short-circuit ───────────────────────────────────────────────
    if fixture:
        return _load_fixture(fixture, "site-check")  # type: ignore[return-value]

    # ── Live F15 adapter ─────────────────────────────────────────────────────
    from app.adapters.site_check import run_site_check

    try:
        return run_site_check(body)
    except Exception as exc:
        logger.error("run_site_check failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Site-check failed: {exc!s}",
        ) from exc


# ---------------------------------------------------------------------------
# Fixture loader
# ---------------------------------------------------------------------------


def _load_fixture(fixture_id: str, endpoint: str) -> Recommendation:
    """Load a frozen golden payload from apps/api/fixtures/<id>.json (AC4).

    Raises HTTP 404 if the fixture file is not found.
    No engine / LLM / DB call is made.
    """
    # Sanitise: no path traversal
    safe_id = Path(fixture_id).name
    fixture_path = _FIXTURES_DIR / f"{safe_id}.json"
    if not fixture_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Fixture '{safe_id}' not found. "
                f"Available: {[p.stem for p in _FIXTURES_DIR.glob('*.json')]}"
            ),
        )
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    if endpoint == "recommend":
        return Recommendation.model_validate(raw)
    elif endpoint == "site-check":
        return SiteCheckResponse.model_validate(raw)  # type: ignore[return-value]
    raise HTTPException(status_code=400, detail=f"Unknown endpoint: {endpoint}")