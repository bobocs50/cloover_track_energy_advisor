# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Heimwende Energy Advisor — an AI home-energy transition advisor (Berlin Energy AI Hackathon 2026, Cloover challenge). It computes one number: **how much a household saves per month** after a full upgrade (solar + battery + heat pump + EV charger) bundled with financing and a dynamic tariff, sold as a single product.

## Monorepo layout

Two apps, two toolchains. **Note:** the directories are `apps/backend` and `apps/frontend`. The root `README.md` "Repository structure" section and the `Makefile` still use the old names `apps/api` / `apps/web` — those `make` targets (`make api-dev`, etc.) `cd` into nonexistent dirs and currently fail. Use the app directories directly with the commands below until the Makefile/README are fixed.

- `apps/backend/` — FastAPI (Python 3.12, **uv**). The only server: it hosts the BFF **and** the pure domain core. All secret keys live here. Has its own [CLAUDE.md](apps/backend/CLAUDE.md) — read it before touching backend code.
- `apps/frontend/` — Vite + React + TS + Tailwind SPA (**pnpm**, registered in `pnpm-workspace.yaml`). TanStack Query, React Hook Form + Zod, Mapbox GL, Three.js / react-three-fiber. Has its own [CLAUDE.md](apps/frontend/CLAUDE.md) — read it before touching frontend code.
- `specs/` — the frozen contract (see "The contract seam" below).
- `docs/feature_track/` — feature backlog, spec-based process, build timeline. Stubs are tagged `TODO F## (owner)`; find a feature's spec there before implementing it.
- `supabase/` — Postgres migrations (`price_catalog`, permit/solar tables, runs, proposals).

## Commands

Backend — run from `apps/backend/`:
```bash
uv sync                                                          # install deps
uv run uvicorn app.main:app --app-dir src --reload --port 8000   # dev server → /docs
uv run pytest                                                    # all tests
uv run pytest tests/unit/domain/test_intake.py -k test_normalise # single test
uv run ruff check . && uv run mypy src                           # lint + type-check
```

Frontend — run from `apps/frontend/`:
```bash
pnpm install
pnpm dev          # Vite on http://localhost:5173
pnpm build        # tsc -b && vite build
pnpm lint         # eslint
pnpm typecheck    # tsc --noEmit
```

Supabase (migrations are idempotent psql files — no Supabase CLI required):
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/202606200001_f04_schema.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/202606210001_f26_subsidy_catalog.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/seed.sql
```

Run backend and frontend in two terminals. Frontend talks to the backend via `VITE_API_BASE_URL` (default `http://localhost:8000`). Append `?fixture=demo-detached` (or `?fixture=nahholz-buchen`) to any `POST /recommend` call to get a golden payload without hitting real APIs.

## The contract seam (read this first)

`specs/` is the source of truth and **wins over** prose docs when they disagree:

- `specs/api/openapi.yaml` (**F02, frozen**) — the HTTP contract. The frontend's TS client (`apps/frontend/src/lib/`) and the backend's Pydantic models (`apps/backend/src/app/domain/models.py`) are both derived from it. Files marked `# FROZEN CONTRACT (F02)` must not diverge. **Any contract change updates the YAML, the backend models, and the frontend types in the same commit** — `make gen-models` / `make gen-client` regenerate them from the YAML.
- `specs/domain/savings-engine.spec.md` (**F03, frozen**) — every formula plus a worked example exported as machine-checkable test vectors (`specs/domain/fixtures/`). The engine is TDD'd against these.

## Cross-cutting invariants

- **The LLM never computes the number.** Claude (provider-agnostic adapter, `apps/backend/src/app/adapters/llm/`) only explains and sells the result. All money math is deterministic domain code.
- **No secrets in the frontend bundle.** The frontend env vars are `VITE_API_BASE_URL` and `VITE_MAPBOX_TOKEN` (a publishable Mapbox token, not a secret); every real API key (Anthropic, Tavily, Supabase service-role, Google) lives in the backend's env via `pydantic-settings` (`apps/backend/src/app/core/config.py`).
- **Domain purity** — `apps/backend/src/app/domain/` must never import from `adapters/`, `api/`, or `services/`. Monetary values are injected via `PricingContext`, never hardcoded in `constants.py`. (Details in the backend CLAUDE.md.)
- **North Star metric** = what the household pays today − (upgrade installment + new energy costs). Where the installment outweighs early savings, that's shown honestly ("near cost-neutral now, €X/month once paid off").

## What actually runs today

Most of the savings ladder (electricity / heating / mobility / financing) is still stubbed. The two engines that run end-to-end live under `apps/backend/src/app/domain/savings/` and each has its own `INFO.md` next to the code — read it before changing that engine:

- `solar_layer/` — address → real Google Solar roof geometry + local irradiance → sized PV offers (Budget / Balanced / Max Independence), backtested against 1,062 real DE projects.
- `permit_layer/` — 12 live German permit checks across solar / heat pump / EV / battery, streamed per-check over SSE (`GET /api/v1/advisor/permits/stream`). Sources: Denkmal WMS, Bebauungsplan (Tavily + Claude), MaStR neighbour count, OSM Overpass, and hardcoded GEG/LBO/TA-Lärm rules.
- `subsidy_layer/` (F26, WIP) — official German subsidy catalog (KfW 458, BAFA, 0 % VAT, optional Länder grants) seeded in `subsidy_catalog` DB table; `catalog.py` queries it, `crawler.py` is the refresh stub.

The frontend's live flow is a 5-step state machine in `apps/frontend/src/features/intake/IntakeScreen.tsx`: address form → Mapbox flyTo → roof-polygon draw → roof params → 3D model (Three.js) + activity feed + `/recommend` call. The post-recommendation screens (`dashboard/`, `results/`, `configurator/`, `proposal/`) are built against the contract but **not yet wired into the flow**. See the frontend [CLAUDE.md](apps/frontend/CLAUDE.md) for the full layout.
