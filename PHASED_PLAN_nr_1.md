# Plan: Live Activity (Frontend ↔ Backend SSE)

Connect the frontend to the backend with a real streaming pipeline run, and build the live activity
feed (per `apps/frontend/data/connection.md`). Excludes the zoom-in 3D bubbles and the `components[]`
contract change. Animations use CSS/Tailwind + a dependency-free SVG graph — **not** Remotion.

## Progress
- [x] Phase 1: Backend event contract + real SSE skeleton (sequential)
- [x] Phase 2: Real parallel orchestration (solar + permits)
- [x] Phase 3: Frontend stream client + state + wiring
- [ ] Phase 4: Polished live UX (animations + SVG pipeline graph)

---

## Phase 1: Backend event contract + real SSE skeleton (sequential)
**Goal:** A streaming endpoint runs the actual recommend pipeline and emits a real `PipelineEvent` per
step, ending with the `Recommendation`.
**Effort:** ~2–3 hours

Steps:
1. Define `PipelineEvent` + enums (`LayerId`, `LayerStatus`, `StepStatus`, event `type`) as Pydantic
   models — subset of `connection.md`. Transport concern → `app/api/schemas/pipeline.py` (NOT `domain/`).
2. Add an orchestrator generator in `app/services/run_stream.py` that wraps the existing
   `RecommendationService` steps and yields events: `run_started` → parent(resolve pricing) →
   ladder layers (solar/battery/heat_pump/ev) → subsidy → LLM → persist → `run_completed`
   (Recommendation in payload). Sequential for now.
3. Add `POST /api/v1/advisor/recommend/stream` returning `StreamingResponse(text/event-stream)`,
   mirroring `permits.py` (`yield f"data: {json}\n\n"`). Honor `?fixture=`.
4. Add a `demo_pacing_ms` setting (`core/config.py`, default 0) — small `asyncio.sleep` between
   emits when > 0, for the demo.
5. Verify with `curl -N` that events stream and the terminal event carries the full Recommendation.

**Risk:** SSE from a POST (household body) — fine server-side; the frontend reads it via fetch
streaming (Phase 3), not `EventSource`. Engine call is sync; wrap with `run_in_executor` to keep the
generator async.

---

## Phase 2: Real parallel orchestration (solar + permits)
**Goal:** Google Solar roof fetch + the 12 permit checks run as genuine parallel workers feeding the
same stream; Solar's site yield flows into the ladder.
**Effort:** ~3–4 hours

Steps:
1. Introduce an `asyncio.Queue` event-bus the SSE generator drains; workers push events to it.
2. Launch solar (`solar_layer` Google Solar roof → `specific_yield`) and permits (`permit_layer`
   engine, ThreadPool) concurrently via `asyncio.create_task` / `run_in_executor`; emit
   `worker_started` / `worker_heartbeat` / `worker_completed` + `layer_completed` with payloads
   (solar `potentialKwp`/yield; permit per-check results).
3. Feed Solar's `specific_yield` into `recommend(...)` so the ladder uses the real site value;
   emit `dependency_waiting` (battery ← solar) and `monitor_notice` (latency) events.
4. Offline-safe: if Google Solar / permits fail or keys are missing, emit `fallback_used` / `error`
   and continue with defaults.
5. Verify with `curl -N`: parallel worker events interleave; run completes with the Recommendation.

**Risk:** mixing threads (permits ThreadPool, sync engine) with asyncio — isolate via
`run_in_executor`. Don't block the event loop. Keep the whole run cancel-safe if the client drops.

---

## Phase 3: Frontend stream client + state + wiring
**Goal:** Frontend consumes the real stream, builds `PipelineRunState`, renders into `ActivityFeed`,
ends on the `Recommendation`; DEV simulates without a backend.
**Effort:** ~3 hours

Steps:
1. Add `src/features/activity/pipeline.ts` — `PipelineEvent`, `LayerId`, statuses, `PipelineRunState`,
   and a reducer `applyEvent(state, event)`.
2. Add `postRecommendStream(household, opts, onEvent)` in `src/lib/api.ts` — `fetch` POST +
   `ReadableStream` SSE parsing.
3. Add `usePipelineRun` hook that opens the stream and reduces events into `PipelineRunState`.
4. DEV path: a simulated event player that emits a scripted sequence then resolves the
   `demo-detached` fixture (keeps no-backend dev working).
5. Wire `IntakeScreen.runRecommend` to the stream; map events → `ActivityEvent` (`toActivityEvent`);
   on `run_completed` set the `Recommendation` (drives the offer page / status pill).
6. Verify in browser preview: feed populates live; offers page renders from the streamed result.

**Risk:** the existing `runRecommend` uses a one-shot `postRecommend`; keep it as the DEV/fallback
path so we never break the no-backend dev flow.

---

## Phase 4: Polished live UX (animations + SVG pipeline graph)
**Goal:** Control-room feel — parallel grouping, transitions, monitor notices — plus a
dependency-free SVG pipeline mini-graph, all from the same stream.
**Effort:** ~3–4 hours

Steps:
1. Enhance `ActivityFeed`: group active workers by layer, status color transitions, enter/exit
   animations (CSS/Tailwind), "N checks running in parallel" indicator, distinct monitor/fallback
   styling, source icons.
2. Build `PipelineGraph` (plain SVG): parent + child layer nodes, pulsing active nodes, packets
   flowing on `layer_completed` / `dependency_resolved`, status badges — driven by `PipelineRunState`.
   No new deps.
3. Place the graph alongside the feed in the `viewing` state of `IntakeScreen`.
4. Respect `prefers-reduced-motion`; avoid layout thrash.
5. Verify in browser: parallel work is visible; graph and feed never disagree (one source of truth).

**Risk:** animation perf with many rapid events — throttle/batch DOM updates; cap retained feed rows.
```
