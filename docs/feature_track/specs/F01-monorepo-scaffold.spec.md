---
id: F01
title: Monorepo scaffold & toolchain
epic: E0 Foundations
owner: Zhou
reviewers: [Lukas]
priority: P0
mvp: true
status: Ready
branch: feat/F01-monorepo-scaffold
depends_on: []
contract_impact: none
estimate_h: 1.5
---

# F01 — Monorepo scaffold & toolchain

> **North-Star link:** This is the floor every other feature stands on — without a clean
> Vite-SPA-only frontend and a `uv`-managed FastAPI backend, nobody can compute, serve, or
> *show* the `monthly_saving`. It moves the headline indirectly by unblocking F02–F04 in P0.

## 1. Intent (what & why)

Stand up the two-app monorepo the whole team builds in: `apps/web` (Vite + React + TS + Tailwind
SPA) and `apps/api` (FastAPI, Python 3.12, `uv`), each with lint/format/test wired and a single root
command to run both. Enforce the §1 architecture rule that **FastAPI is the only server and is the
BFF** — Vite removes the Next.js server tier. **Critically, delete the stale Next.js `apps/web/.next/`
build artifacts and ensure no Next.js dependency remains** (locked decision D2). Refs §1.

## 2. Scope

**In scope**
- `apps/web`: Vite + React + TypeScript + Tailwind SPA scaffold (§1 frontend row).
- `apps/api`: FastAPI on Python 3.12 managed by `uv` (§1 backend row), owning the pure domain core **and** acting as BFF.
- Tooling: backend `ruff` (lint+format) + `mypy` (types) + `pytest`; frontend `eslint` + `tsc` + `vitest`.
- Root run scripts: one command to start FE+BE for dev; one to run all checks (lint/type/test) across both apps.
- Env hygiene: FE ships **only** `VITE_API_BASE_URL`; all keys (Anthropic, Google, Supabase service-role) live in FastAPI env (§1, §11). Provide `.env.example` documenting both sides.
- CORS allows the Vite dev origin `http://localhost:5173` + deployed origin only (§1).
- **Cleanup (D2):** delete `apps/web/.next/` and its stale `node_modules`; confirm no `next` dependency anywhere in the FE toolchain.

**Out of scope** (explicitly, to prevent creep)
- The OpenAPI contract + generated TS client → **F02**.
- Supabase schema / `price_catalog` seed → **F04**.
- Any domain logic, endpoints, or UI screens → E1/E2/E3 features.
- CI/CD pipeline config (a local "all checks" script suffices for the hackathon).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | `apps/web` is a Vite + React + TS + Tailwind SPA; `npm/pnpm` dev server starts on `:5173`. | §1 (frontend) |
| R2 | `apps/api` is a FastAPI app on Python 3.12, dependency-managed by `uv`; dev server starts (e.g. `:8000`). | §1 (backend) |
| R3 | Backend checks run clean on the scaffold: `ruff` (lint+format), `mypy`, `pytest`. | §1 |
| R4 | Frontend checks run clean on the scaffold: `eslint`, `tsc --noEmit`, `vitest`. | §1 |
| R5 | A single root script starts FE+BE together; a single root script runs all lint/type/test across both apps. | §1 (BFF/dev ergonomics) |
| R6 | The only `VITE_*` var is `VITE_API_BASE_URL`; no secret/key is referenced in any FE file or `VITE_*` var. | §1, §11 |
| R7 | `.env.example` exists documenting FE (`VITE_API_BASE_URL`) and BE (key placeholders) separately. | §1 |
| R8 | CORS on FastAPI allows exactly `http://localhost:5173` + the deployed origin. | §1 |
| R9 | `apps/web/.next/` is deleted and no `next` package appears in FE dependencies or lockfile (D2). | §1, D2 / Backlog §6 |

## 4. Data, formulas & sources

N/A — pure scaffolding/plumbing. This feature computes and fetches nothing; it reads no `price_catalog`
values. The only "constants" are infrastructure choices fixed by §1 (ports `5173`/`8000`, the single
`VITE_API_BASE_URL` var) — these are infrastructure config, not domain numbers.

## 5. Contract surface

`contract_impact: none` — F01 creates no `specs/api/openapi.yaml` and touches no schema. It only
establishes the directory layout that F02 will populate. (Backwards-compatible by definition: nothing
exists to break.)

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1** — Given a clean checkout, when the root "dev" script runs, then the Vite SPA serves on `http://localhost:5173` and FastAPI serves on its port, both reachable.
- [ ] **AC2** — Given the scaffold, when the root "check" script runs, then `ruff`, `mypy`, `pytest` (api) and `eslint`, `tsc`, `vitest` (web) all exit 0.
- [ ] **AC3** — Given the FE source tree, when grepped for `VITE_`, then the only variable referenced is `VITE_API_BASE_URL`, and no Anthropic/Google/Supabase key string appears in any FE file or `VITE_*` var.
- [ ] **AC4 (honesty/edge — D2 cleanup)** — Given the repo, when checked, then `apps/web/.next/` does not exist and no `next` entry appears in the FE `package.json` or lockfile.
- [ ] **AC5** — Given a request from `http://localhost:5173`, when it hits FastAPI, then CORS permits it; given an arbitrary disallowed origin, then CORS rejects it.
- [ ] **AC6** — Given the repo root, when listed, then `.env.example` exists and documents FE and BE env separately, with no real secret values.

## 7. Test plan

- **Unit** (pure plumbing): a trivial `pytest` (e.g. a health-route or sanity assert) and a trivial `vitest` (e.g. a render-or-truthy assert) prove the test runners are wired.
- **Integration / contract**: hit the FastAPI health endpoint from a test asserting 200; assert CORS headers for the allowed origin. No contract yet (F02).
- **Demo-safety**: confirm `.env.example` boots the apps with placeholder values; FE has zero hard dependency on any key to render the shell.

## 8. Dependencies & interfaces

- **Upstream (needs):** nothing (`depends_on: []`); this is the root of the dependency graph (Backlog §4).
- **Downstream (feeds):** **F02** (contract + client live in this layout), **F04** (Supabase wiring uses the api app), and all of E1/E2/E3 build inside these apps.
- **Mock until ready:** N/A — F01 is the thing others mock against (the directory + run scripts).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Stale Next.js scaffold contradicts the Vite decision (D2) | F01 deletes `apps/web/.next/` and its `node_modules`; rebuild as Vite; verify no `next` dep (AC4) — Backlog §6, §15. |
| A secret leaks into the Vite bundle | Only `VITE_API_BASE_URL` client-side; all keys in FastAPI env; AC3 greps for leaks (§1, §15). |
| Tool versions drift between machines | Pin Python 3.12 + `uv` lockfile and the FE lockfile so the whole team is reproducible (§1). |
| CORS misconfig blocks the demo or opens it wide | Allowlist exactly `:5173` + deployed origin (AC5), per §1. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (or a documented manual check for pure scaffolding).
- [ ] Lint + type-check clean (`ruff`+`mypy` / `eslint`+`tsc`).
- [ ] Contract honored — N/A (`contract_impact: none`); no `openapi.yaml` touched.
- [ ] No secret added to the frontend bundle; no hard-coded price (none applicable — no `price_catalog` use).
- [ ] Every figure traces to a source or a labelled assumption — N/A (no domain figures).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path scaffold (both apps boot, checks pass) still works after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §1 (tech stack, no-secrets, BFF), §11 (keys server-side only).
- Backlog `FEATURE_BACKLOG.md` §2 D2 (Vite decision, clear `.next/`), §6 (program risk: stale scaffold).
- `specs/api/openapi.yaml` — created by F02 (not this feature).
