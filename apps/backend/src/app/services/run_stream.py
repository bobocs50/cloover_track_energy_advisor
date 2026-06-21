"""Streaming recommendation orchestrator — the live-run event source.

Owner: backend
Feature: live activity stream (frontend ↔ backend connection)

Runs the SAME pipeline as ``RecommendationService.run`` (resolver → engine → LLM → persist)
but as an **async generator that yields SSE frames** so the frontend can show what the backend
is actually doing, step by step.

Phase 1: real steps, sequential. The genuinely-parallel external layers (Google Solar roof +
permit checks) are folded in by Phase 2. Blocking work is offloaded to a thread executor so the
event loop (and the stream) stays responsive.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from functools import partial
from pathlib import Path

from app.api.schemas.pipeline import EventBuilder, PipelineEvent, sse
from app.core.config import Settings, get_settings
from app.domain.models import Household, Recommendation

logger = logging.getLogger(__name__)

# services/run_stream.py → parents[3] = apps/backend → fixtures/
_FIXTURES_DIR = Path(__file__).parents[3] / "fixtures"

# Ladder rung index → the product layer it introduces (solar→battery→hp→ev).
_RUNG_LAYER: list[tuple[str, str]] = [
    ("solar", "Solar"),
    ("battery", "Battery"),
    ("heat_pump", "Heat pump"),
    ("ev_charger", "EV charger"),
]

# Berlin centre — geocode fallback so the run survives an offline/no-key environment.
_BERLIN_FALLBACK: tuple[float, float] = (52.52, 13.405)

# PermitCheck.status → pipeline event Status.
_PERMIT_STATUS: dict[str, str] = {
    "pass": "accepted",
    "warn": "warn",
    "fail": "rejected",
    "info": "ok",
}


async def _pace(settings: Settings) -> None:
    """Optional demo throttle so each step is legible (0 = off, real speed)."""
    ms = getattr(settings, "demo_pacing_ms", 0)
    if ms > 0:
        await asyncio.sleep(ms / 1000)


async def _run[T](fn: Callable[..., T], *args: object) -> T:
    """Run blocking work in the default thread executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(fn, *args))


def _ladder_events(eb: EventBuilder, rec: Recommendation) -> list[PipelineEvent]:
    """Derive one real `layer_completed` per ladder rung from the computed result.

    Per-layer Δ = alternatives[n].monthly_saving − alternatives[n-1].monthly_saving.
    """
    events: list[PipelineEvent] = []
    prev = 0.0
    for idx, alt in enumerate(rec.alternatives[: len(_RUNG_LAYER)]):
        layer_id, label = _RUNG_LAYER[idx]
        delta = alt.monthly_saving_eur - prev
        prev = alt.monthly_saving_eur
        if idx > 0:
            events.append(
                eb.make(
                    "dependency_resolved",
                    layer_id,  # type: ignore[arg-type]
                    "running",
                    f"{label} / inputs ready",
                    parent_layer_id=_RUNG_LAYER[idx - 1][0],
                    source="engine",
                )
            )
        events.append(
            eb.make(
                "layer_completed",
                layer_id,  # type: ignore[arg-type]
                "accepted",
                f"{label} / +€{delta:.0f}/mo",
                detail=f"cumulative €{alt.monthly_saving_eur:.0f}/mo at {alt.scenario_id}",
                source="engine",
                payload={
                    "scenarioId": alt.scenario_id,
                    "deltaEurMonth": round(delta, 1),
                    "cumulativeEurMonth": round(alt.monthly_saving_eur, 1),
                },
            )
        )
    return events


async def _site_analysis_events(
    eb: EventBuilder, household: Household, settings: Settings, state: dict[str, float]
) -> AsyncIterator[PipelineEvent]:
    """Run Google Solar roof ∥ the 12 permit checks as real parallel workers.

    Every worker is offline-safe: failures degrade to a fallback event, never kill the
    run. Writes ``state['specific_yield']`` (site PV yield) for the ladder, plus lat/lng.
    """
    from dataclasses import asdict

    from app.domain.constants import SPECIFIC_YIELD_FALLBACK
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
    from app.domain.savings.solar_layer.google_solar import (
        GoogleSolarError,
        _fetch_building_insights,
        geocode,
        parse_roof,
    )

    addr = household.address
    address_str = f"{addr.street} {addr.house_no}, {household.plz} {addr.city}".strip()
    bundesland = plz_to_bundesland(household.plz)
    fuel = getattr(household.heating.fuel, "value", str(household.heating.fuel))

    # ── Geocode the address (gates both branches; permits reuse the coords) ─────
    yield eb.make("step_started", "parent", "running", "Geocoding address",
                  step_id="geocode", detail=address_str, source="google_solar")
    try:
        lat, lng = await _run(partial(geocode, address_str, settings.google_geocoding_api_key))
    except Exception as exc:
        lat, lng = _BERLIN_FALLBACK
        yield eb.make("fallback_used", "parent", "warn", "Geocode fallback (Berlin centre)",
                      step_id="geocode", detail=str(exc), source="google_solar")
    state["lat"], state["lng"] = lat, lng
    yield eb.make("step_completed", "parent", "ok", f"Located at {lat:.4f}, {lng:.4f}",
                  step_id="geocode", source="google_solar")

    # ── Launch parallel workers (Solar roof + 12 permit checks) ────────────────
    queue: asyncio.Queue[PipelineEvent | object] = asyncio.Queue()
    sentinel = object()

    yield eb.make("worker_started", "solar", "running", "Google Solar / fetching roof",
                  worker_id="google_solar", source="google_solar")
    yield eb.make("layer_started", "permit", "running", "Running 12 permit checks",
                  detail="LBO / Denkmalschutz / B-Plan / MaStR / GEG / TA-Lärm / WEG",
                  source="internet")

    async def solar_worker() -> None:
        try:
            insights = await _run(
                partial(_fetch_building_insights, lat, lng, settings.google_solar_api_key)
            )
            roof = parse_roof(insights)
            if roof is None:
                raise GoogleSolarError("no Solar coverage at this location")
            state["specific_yield"] = roof.specific_yield_kwh_per_kwp
            await queue.put(eb.make(
                "worker_completed", "solar", "accepted",
                f"Roof / {roof.max_modules} panels / {roof.dominant_orientation} / "
                f"{roof.specific_yield_kwh_per_kwp:.0f} kWh/kWp",
                worker_id="google_solar", source="google_solar",
                payload={
                    "maxModules": roof.max_modules,
                    "orientation": roof.dominant_orientation,
                    "specificYield": round(roof.specific_yield_kwh_per_kwp, 1),
                    "usableAreaM2": round(roof.usable_area_m2, 1),
                    "source": roof.source,
                },
            ))
        except Exception as exc:
            state["specific_yield"] = SPECIFIC_YIELD_FALLBACK
            await queue.put(eb.make(
                "fallback_used", "solar", "warn",
                f"Google Solar fallback / {SPECIFIC_YIELD_FALLBACK:.0f} kWh/kWp",
                worker_id="google_solar", detail=str(exc), source="google_solar",
                payload={"specificYield": SPECIFIC_YIELD_FALLBACK},
            ))

    PermitFn = Callable[..., "PermitCheck | list[PermitCheck]"]
    permit_jobs: list[tuple[PermitFn, tuple[object, ...]]] = [
        (check_solar_lbo, (bundesland,)),
        (check_denkmal_solar, (lat, lng, bundesland)),
        (check_denkmal_heatpump, (lat, lng, bundesland)),
        (check_bplan, (household.plz, addr.city, settings.tavily_api_key,
                       settings.anthropic_api_key)),
        (check_mastr, (household.plz, settings.supabase_url,
                       settings.supabase_service_role_key, settings.tavily_api_key)),
        (check_ev_parking, (lat, lng, False)),
        (check_ev_weg, (lat, lng)),
        (check_hp_geg, (household.building_year, fuel)),
        (check_hp_noise, (lat, lng)),
        (check_battery_install, ()),
        (check_battery_mastr, ()),
    ]

    async def permit_worker(fn: PermitFn, args: tuple[object, ...]) -> None:
        try:
            res = await _run(partial(fn, *args))
            checks: list[PermitCheck] = res if isinstance(res, list) else [res]
            for ch in checks:
                await queue.put(eb.make(
                    "worker_completed", "permit", _PERMIT_STATUS.get(ch.status, "ok"),  # type: ignore[arg-type]
                    ch.label, worker_id=ch.id, detail=ch.detail, source="internet",
                    payload=asdict(ch),
                ))
        except Exception as exc:
            await queue.put(eb.make(
                "worker_completed", "permit", "warn", f"{getattr(fn, '__name__', 'check')} failed",
                detail=str(exc), source="internet",
            ))

    workers = [asyncio.create_task(solar_worker())]
    workers += [asyncio.create_task(permit_worker(fn, args)) for fn, args in permit_jobs]

    async def _close_when_done() -> None:
        await asyncio.gather(*workers, return_exceptions=True)
        await queue.put(sentinel)

    closer = asyncio.create_task(_close_when_done())

    while True:
        item = await queue.get()
        if item is sentinel:
            break
        assert isinstance(item, PipelineEvent)
        yield item
    await closer

    state.setdefault("specific_yield", SPECIFIC_YIELD_FALLBACK)
    yield eb.make("layer_completed", "permit", "accepted", "Permit checks complete",
                  source="internet")
    yield eb.make("dependency_resolved", "solar", "running", "Site yield ready for the ladder",
                  source="engine", payload={"specificYield": round(state["specific_yield"], 1)})


def _load_fixture(fixture_id: str) -> Recommendation:
    safe = Path(fixture_id).name
    path = _FIXTURES_DIR / f"{safe}.json"
    if not path.exists():
        raise FileNotFoundError(f"fixture '{safe}' not found in {_FIXTURES_DIR}")
    import json

    return Recommendation.model_validate(json.loads(path.read_text(encoding="utf-8")))


async def stream_recommendation(
    household: Household,
    fixture: str | None = None,
    settings: Settings | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for one recommendation run, ending with the Recommendation."""
    settings = settings or get_settings()
    eb = EventBuilder(run_id=uuid.uuid4().hex[:12])

    yield sse(eb.make("run_started", "parent", "running", "Starting recommendation run"))
    await _pace(settings)

    try:
        if fixture:
            async for frame in _stream_fixture(eb, fixture, settings):
                yield frame
            return

        async for frame in _stream_live(eb, household, settings):
            yield frame
    except Exception as exc:  # never leave the stream hanging
        logger.error("stream_recommendation failed: %s", exc, exc_info=True)
        yield sse(
            eb.make("run_error", "parent", "error", "Run failed", detail=str(exc), source="engine")
        )


async def _stream_live(
    eb: EventBuilder, household: Household, settings: Settings
) -> AsyncIterator[str]:
    from app.adapters.llm.base import assert_numbers_grounded
    from app.adapters.llm.factory import make_advisor
    from app.adapters.resolver import Resolver
    from app.domain.savings.engine import recommend
    from app.domain.savings.subsidy_layer.catalog import resolve_subsidies

    # ── Parent: resolve price catalog ──────────────────────────────────────────
    yield sse(
        eb.make(
            "step_started", "parent", "running",
            "Resolving price catalog", step_id="resolve_pricing",
            detail=f"PLZ {household.plz} / tariffs, capex, financing", source="database",
        )
    )
    resolver = Resolver(settings=settings)
    ctx, _assumptions = await _run(resolver.resolve_pricing, household.plz)
    await _pace(settings)
    yield sse(
        eb.make(
            "step_completed", "parent", "ok",
            "Price catalog resolved", step_id="resolve_pricing", source="database",
        )
    )

    # ── Subsidy layer (KfW/BAFA/VAT) ───────────────────────────────────────────
    yield sse(
        eb.make("layer_started", "subsidy", "running", "Checking subsidy catalog",
                source="supabase")
    )
    subsidies = await _run(
        partial(
            resolve_subsidies,
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_role_key,
        )
    )
    await _pace(settings)
    yield sse(
        eb.make("layer_completed", "subsidy", "accepted", "Subsidy catalog applied",
                detail="KfW 458 / BAFA / 0% VAT resolved.", source="supabase")
    )

    # ── Parallel site analysis: Google Solar roof ∥ 12 permit checks ───────────
    site: dict[str, float] = {}
    async for ev in _site_analysis_events(eb, household, settings, site):
        yield sse(ev)
        await _pace(settings)
    specific_yield = site["specific_yield"]

    # ── Engine: cumulative savings ladder (uses the real site yield) ───────────
    yield sse(
        eb.make("layer_started", "solar", "running", "Computing savings ladder",
                detail=f"solar / battery / heat pump / ev at {specific_yield:.0f} kWh/kWp",
                source="engine")
    )
    rec: Recommendation = await _run(
        partial(recommend, household, ctx, specific_yield=specific_yield, subsidies=subsidies)
    )
    for ev in _ladder_events(eb, rec):
        yield sse(ev)
        await _pace(settings)

    # ── LLM advisor (explain / sell) + number guard ────────────────────────────
    yield sse(
        eb.make("layer_started", "financing", "running", "Writing the proposal",
                detail="LLM explains the numbers (never computes them).", source="llm")
    )
    advisor = make_advisor(settings)
    payload = rec.model_dump()
    copy = await _run(advisor.explain, payload, household.locale)
    all_text = " ".join(str(v) for v in copy.values())
    if not assert_numbers_grounded(all_text, payload):
        from app.adapters.llm.stub import StubAdvisor

        yield sse(
            eb.make("fallback_used", "financing", "warn", "Ungrounded figure — using safe copy",
                    detail="LLM emitted a number not in the payload; fell back to stub.",
                    source="llm")
        )
        copy = await _run(StubAdvisor().explain, payload, household.locale)
    rec = rec.model_copy(
        update={
            "explanation_md": copy.get("explanation_md", rec.explanation_md),
            "proposal_copy_md": copy.get("proposal_copy_md", rec.proposal_copy_md),
            "upsell": rec.upsell.model_copy(
                update={"reason_md": copy.get("upsell_reason_md", rec.upsell.reason_md)}
            ),
        }
    )
    await _pace(settings)
    yield sse(eb.make("layer_completed", "financing", "accepted", "Proposal ready", source="llm"))

    # ── Best-effort persistence ────────────────────────────────────────────────
    from app.services.recommendation import RecommendationService

    await _run(RecommendationService(settings=settings)._persist, household, rec)

    # ── Done — final payload rides the terminal event ──────────────────────────
    yield sse(
        eb.make(
            "run_completed", "parent", "accepted",
            f"Done / €{rec.best.monthly_saving_eur:.0f}/mo / {rec.best.scenario_id}",
            source="engine", payload={"recommendation": rec.model_dump()},
        )
    )


async def _stream_fixture(
    eb: EventBuilder, fixture: str, settings: Settings
) -> AsyncIterator[str]:
    """Stream a canned-but-real event sequence off a golden fixture (no engine/LLM/DB)."""
    rec = await _run(_load_fixture, fixture)
    yield sse(
        eb.make("step_completed", "parent", "ok", "Loaded golden fixture",
                step_id="resolve_pricing", detail=fixture, source="database")
    )
    await _pace(settings)
    yield sse(eb.make("layer_completed", "subsidy", "accepted", "Subsidy catalog applied",
                      source="supabase"))
    await _pace(settings)
    for ev in _ladder_events(eb, rec):
        yield sse(ev)
        await _pace(settings)
    yield sse(eb.make("layer_completed", "financing", "accepted", "Proposal ready", source="llm"))
    await _pace(settings)
    yield sse(
        eb.make(
            "run_completed", "parent", "accepted",
            f"Done / €{rec.best.monthly_saving_eur:.0f}/mo / {rec.best.scenario_id}",
            source="engine", payload={"recommendation": rec.model_dump()},
        )
    )
