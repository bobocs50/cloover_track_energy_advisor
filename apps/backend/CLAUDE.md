# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands must be run from `apps/backend/`.

```bash
# Install dependencies
uv sync

# Run the dev server (auto-reload)
uv run uvicorn app.main:app --app-dir src --reload --port 8000

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/unit/domain/test_intake.py

# Run a single test by name
uv run pytest tests/unit/domain/test_intake.py -k "test_normalise"

# Lint + type-check
uv run ruff check .
uv run mypy src
```

`pythonpath = ["src"]` is set in `pyproject.toml` so tests import `app.*` directly without a package install step.

## Context

- [`data/hackathon_track.md`](data/hackathon_track.md) — hackathon criteria: the North Star, three saving buckets, up-sell requirement, AI angle
- [`data/goal.md`](data/goal.md) — full user journey: Mapbox → 3D roof → permits → Layer 1–4 → dashboard
- [`data/layers.md`](data/layers.md) — the 5 implementation layers (Site-Check + L1→L4) with formulas, status, and build order

Read these before touching any savings engine code.

## Architecture

The codebase is split by layer, each with a strict ownership rule:

```
src/app/
├── domain/        # Pure-ish — engine logic. Input: Household + PricingContext → Recommendation.
│   ├── models.py  # Frozen Pydantic v2 contract (F02). Source of truth for all types.
│   ├── constants.py  # Physics constants only. Monetary values go in PricingContext.
│   └── savings/   # The savings ladder + the two real engines.
│       ├── intake.py        # F05: normalise Household → NormalisedHousehold + assumptions[]
│       ├── engine.py        # orchestrate the savings ladder (mostly stubs)
│       ├── electricity_layer/heatpump_layer/ev_layer.py  # Layer 2/3/4 bucket math
│       ├── financing.py / options.py / scenarios.py / engine.py  # ladder orchestration
│       ├── solar_layer/     # Layer 1 — Google Solar roof data → sized PV offers (see its INFO.md)
│       │   ├── google_solar.py  # address → real roof geometry + local irradiance
│       │   ├── pipeline.py      # sizing + physics + 3-offer generation engine
│       │   ├── physics.py / economics.py
│       │   └── merged_input_output.csv  # 1,062 real DE projects for backtest
│       ├── permit_layer/    # Step 2 — 12 live permit checks (see its INFO.md)
│       │   ├── checks.py        # 11 check fns (1 returns 2) → 12 PermitChecks
│       │   └── engine.py        # ThreadPool fan-out → PermitMatrix + Supabase cache
│       └── subsidy_layer/  # F26 — official subsidy catalog (KfW 458/BAFA/VAT/Länder)
│           ├── catalog.py       # queries subsidy_catalog DB → SubsidyContext for F11
│           └── crawler.py       # periodic refresh stub (🔶 stretch)
├── adapters/      # All external I/O. No business logic.
│   ├── supabase.py      # PostgREST client using SERVICE_ROLE key
│   ├── resolver.py      # PLZ → PricingContext (reads price_catalog from Supabase)
│   ├── site_check.py    # Roof / permit feasibility
│   ├── irradiance/      # PVGIS yield data
│   ├── tariff/          # Electricity tariff data
│   └── llm/             # LLM adapter (Anthropic / OpenAI / stub)
├── api/
│   ├── routes/advisor.py   # POST /api/v1/advisor/recommend + /site-check (F02 contract)
│   ├── routes/permits.py   # POST /advisor/permits + GET /advisor/permits/stream (SSE, per-check)
│   ├── routes/subsidies.py # GET /advisor/subsidies — subsidy catalog query (F26)
│   ├── routes/health.py
│   └── deps.py             # FastAPI dependency providers
├── services/
│   └── recommendation.py  # Wires resolver → engine → llm → persist (F17)
├── jobs/
│   └── seed_mastr.py       # offline seed for the plz_solar_count table (MaStR neighbour counts)
└── core/config.py          # pydantic-settings; all secrets live here, never in frontend
```

`solar_layer/` and `permit_layer/` are the two engines that actually run end-to-end today; the
electricity_layer/heatpump_layer/ev_layer ladder modules implement the bucket math. Each engine has its
own `INFO.md` next to the code — read it before changing that engine.

### Key invariant: domain purity

`domain/` must never import from `adapters/`, `api/`, or `services/`. The engine receives a fully populated `PricingContext` injected by the adapter layer. Monetary prices never go in `constants.py`.

### Data flow

```
POST /recommend
  → advisor.py route
  → RecommendationService.run()          (services/)
  → Resolver.resolve(plz)                (adapters/) → PricingContext
  → normalise_household(household, ctx)  (domain/savings/intake.py) → NormalisedHousehold
  → recommend(household, ctx)            (domain/savings/engine.py) → Recommendation
  → LLM adapter                          (adapters/llm/) → explanation_md, proposal_copy_md
  → persist to Supabase                  (adapters/supabase.py)
```

### Models are a frozen contract

`domain/models.py` matches `specs/api/openapi.yaml` exactly (F02). Do not add fields without updating both the spec and the TypeScript types in `apps/frontend/src/lib/types.ts`. The comment `# FROZEN CONTRACT (F02)` marks files that should not diverge.

### Stubs and TODO markers

Most engine and service functions raise `NotImplementedError` with a `TODO F##` tag referencing the feature backlog at `docs/feature_track/`. When implementing a feature, find its spec at `docs/feature_track/specs/F##-*.spec.md`.

### Fixture support

`fixtures/demo-detached.json` and `fixtures/nahholz-buchen.json` are golden payloads for `POST /recommend?fixture=<name>` (F24, not yet wired). Use them for frontend development before the engine is complete.

### Tests

```
tests/
├── conftest.py          # FastAPI TestClient fixture (client)
├── unit/
│   ├── domain/          # TDD against specs/domain/fixtures/ vectors
│   └── adapters/        # adapter unit tests
└── integration/
    ├── test_health.py
    └── test_permits.py
```

Unit tests import `app.*` directly (no install needed — `pythonpath = ["src"]` in `pyproject.toml`). Integration tests use the `client` fixture from `conftest.py`.



### Settings

Copy `.env.example` to `.env`. `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are required for any adapter that hits Supabase. `CORS_ORIGINS` defaults to `http://localhost:5173` (the Vite dev server).
