---
id: F17
title: API endpoints /recommend + /site-check
epic: E2 Backend & Adapters
owner: Zhou
reviewers: [Lukas]
priority: P3
mvp: true
status: Ready
branch: feat/F17-api-endpoints
depends_on: [F02, F11, F12]
contract_impact: reads
estimate_h: 2
---

# F17 — API endpoints /recommend + /site-check

> **North-Star link:** This is the wire that delivers `monthly_saving` to the SPA — it orchestrates
> resolver → engine → advisor → persistence and returns the `Recommendation` whose `alternatives[]` are
> the four ladder rungs the configurator turns into per-layer "+€X/mo".

## 1. Intent (what & why)

Implement the two POST endpoints to the **frozen schema** (F02): `/api/v1/advisor/recommend` and
`/api/v1/advisor/site-check`. `/recommend` wires **resolver (F12) → pure engine (F06–F11) → LLM advisor
(F16) → persistence** (`advise_run`, `proposal`) and returns `Recommendation { best, alternatives[]=4
ladder steps, upsell }` (§14.1). `/site-check` returns the F15 payload (§14.2). A **`?fixture=<id>`**
path returns a frozen golden payload for demo determinism (§1). **CORS** allows the Vite origin only;
runs are persisted (§14.3).

## 2. Scope

**In scope**
- `POST /api/v1/advisor/recommend` → `Recommendation{best, alternatives[], upsell}`; `alternatives[]` = the **four cumulative ladder steps** (= the 4 contract scenarios) (§14.1, D3).
- Orchestration: resolver (F12) → engine (F06–F11) → LLM (F16) → persist `advise_run` + `proposal` (§2, §14.3).
- `POST /api/v1/advisor/site-check` → `{roof_ok, feasibility_flags[], energy_context, assumptions[]}` (calls F15) (§14.2).
- **`?fixture=<id>`** on `/recommend` → a **frozen** golden payload, no engine/LLM/DB call (determinism, §1).
- **CORS** allow-list: `http://localhost:5173` (Vite dev) + the deployed origin only (§1).
- **Implements the frozen F02 contract** — F02 already froze the full `Household` (incl. existing-equipment + `selection`) and the `Recommendation`/`ScenarioResult`/`SiteCheckResponse` schemas. F17 adds **no** field (`contract_impact: reads`); if a genuine gap is found, it is a reviewed F02 PR, not an F17 side-change.
- **Early sub-task F17a (P1/H+5):** stand up `/recommend` returning a `?fixture` golden payload (no engine) to unblock Philips immediately; the full engine wiring lands at P3.

**Out of scope** (explicitly, to prevent creep)
- The engine math (F06–F11), the resolver (F12), Site-Check logic (F15), LLM prose (F16) — F17 only **wires** them.
- The §14.3 table DDL/seed → **F04** (F17 writes `advise_run`/`proposal` rows).
- Frozen-payload *capture for the FE demo* / 90-sec happy path → **F24** (F17 provides the `?fixture` mechanism + a seed payload).
- Frontend client generation → **F02/F18**.

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | `POST /api/v1/advisor/recommend` returns `Recommendation{best, alternatives[], upsell}` to the frozen schema. | §14.1 |
| R2 | `alternatives[]` = the **four** cumulative ladder `ScenarioResult`s, each with `breakdown{electricity,heating,mobility}_eur_month`, `installment_eur_month`, `monthly_saving_eur`, `payback_note`. | §14.1, §6.1 |
| R3 | Orchestrate resolver → engine → LLM → persist `advise_run` (household/options/recommendation) + `proposal` (`copy_md`). | §2, §14.3 |
| R4 | `POST /api/v1/advisor/site-check` returns `{roof_ok, feasibility_flags[], energy_context, assumptions[]}` (F15). | §14.2 |
| R5 | `?fixture=<id>` on `/recommend` returns a **frozen** golden payload with **no** engine/LLM/DB call. | §1, §15 |
| R6 | CORS allows the Vite dev origin (`http://localhost:5173`) + the deployed origin only; no secret in any response. | §1, §11 |
| R7 | Implement both endpoints against the **frozen F02 contract** — validate requests/responses to the generated Pydantic models; add no schema field (F02 already froze the full `Household` incl. existing-equipment + `selection`). | §14.1, F02 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> F17 computes **no number** — it orchestrates and serialises. The per-layer "+€X/mo" the UI shows is
> **the difference between consecutive `monthly_saving_eur` values** in `alternatives[]` (§6.1) — no
> extra call. No price is read here (they entered via F12's `PricingContext`).

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `/recommend` | `POST /api/v1/advisor/recommend` | §14.1 contract (F02) | `?fixture` golden payload | pipeline · Recommendation |
| `/site-check` | `POST /api/v1/advisor/site-check` | §14.2 contract (F02) | F15 fallbacks (checkbox/⚪) | pre-step · feasibility |
| per-layer +€/mo | `Δ = monthly_saving_eur[n] − [n−1]` | §6.1 | — | configurator · per-rung |
| persistence | `advise_run`, `proposal` | §14.3 schema (F04) | in-memory if DB down | runs · audit/proposal |

```
# Pipeline (§2), copied verbatim so there is one definition:
#   INTAKE → SITE-CHECK → RESOLVER (enrich §10–12) → L1+Solar ▸ L2+Battery ▸ L3+HP ▸ L4+EV (pure engine)
#   → OPTIMISER (max net) → ADVISOR (LLM proposal).
# /recommend wiring: resolve(PLZ)→PricingContext (F12) → engine ladder (F06–F11) → optimiser best+upsell (F10)
#   → LLM copy (F16, guarded) → persist advise_run + proposal (F04 tables) → return Recommendation.
# alternatives[] = 4 cumulative rungs; configurator +€X/mo = consecutive monthly_saving_eur diffs (§6.1).
# ?fixture=<id> short-circuits to a frozen golden payload (§1) — no engine/LLM/DB call.
```

## 5. Contract surface  *(contract_impact = reads — F02 is the sole author)*

- F17 **reads** the frozen contract; it changes **no** schema. F02 already froze the full `Household`
  (incl. `address{street,house_no,city}`, `floor_area_m2`, `building_year`, `existing_pv_kwp`,
  `existing_battery_kwh`, `existing_heatpump_year?`, `existing_ev`, `existing_ev_charger`,
  `mobility.km_month`, `selection{}`) and the `Recommendation`/`ScenarioResult`/`SiteCheckResponse`
  schemas with their typed leaves. The two edge cases (old-HP, EV-without-charger) are resolved
  **server-side from existing fields** — no new endpoint, no new field (§14.1, §3.2).
- New/changed schema objects: **none.** F17 implements the endpoints to F02's models.
- Backwards-compatible? N/A — no contract change. If F17 finds a missing field, that is a reviewed
  **F02** PR (bumping the TS client there), keeping a single contract author (Backlog §6).

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (recommend shape)** — Given a valid `Household`, when `POST /recommend`, then the body validates against the frozen `Recommendation` schema with `best`, `alternatives[]` of **length 4**, and `upsell`.
- [ ] **AC2 (ladder marginals sum)** — Given the §8 demo household, when `/recommend` returns, then consecutive `alternatives[].monthly_saving_eur` diffs reproduce the §8 per-layer deltas (Solar −€24, Battery ≈€0, HP +€20… cumulative **+€120/mo**) within ±€2, and `best` = the **full ladder** (§8, §6.4).
- [ ] **AC3 (orchestration + persistence)** — Given a `/recommend` call, when it succeeds, then one `advise_run` row (household/options/recommendation) and one `proposal` row (`copy_md` from F16) are written (§14.3).
- [ ] **AC4 (fixture determinism)** — Given `?fixture=<id>`, when `/recommend` is called, then the **exact frozen payload** is returned byte-identically with **no** engine/LLM/DB call (§1).
- [ ] **AC5 (site-check)** — Given a full address, when `POST /site-check`, then the body validates against the frozen `{roof_ok, feasibility_flags[], energy_context, assumptions[]}` (F15) (§14.2).
- [ ] **AC6 (CORS + no-secret)** — Given a request from `http://localhost:5173`, when handled, then CORS allows it (a foreign origin is rejected) and **no** API key/service-role secret appears in any response (§1, §11).
- [ ] **AC7 (honesty/edge — degrade not block)** — Given an unknown PLZ / LLM offline / DB down, when `/recommend` is called, then it still returns a valid `Recommendation` (resolver fallbacks + templated LLM copy + in-memory persist), with labelled assumptions — never a hard failure (§3.4, §15).

## 7. Test plan

- **Unit** (orchestration with mocked resolver/engine/LLM): AC2 marginal-diff assembly on the §8 fixture; AC4 fixture short-circuit; AC7 degrade paths.
- **Integration / contract**: schema-validate both responses against the frozen `openapi.yaml` (F02); assert a full `Household` round-trips through the generated client; assert `advise_run`/`proposal` writes (AC3) against seeded F04 tables; CORS allow/deny (AC6).
- **Demo-safety**: `?fixture` golden payload returns offline (AC4); full pipeline degrades with no network (AC7); this is the seam F24's 90-sec happy path builds on (§15).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F02** (frozen schema + client), **F12** (resolver/`PricingContext`), **F11** (engine output incl. financing/band), F06–F10 (ladder), **F15** (`/site-check` body), **F16** (LLM copy), **F04** (`advise_run`/`proposal` tables).
- **Downstream (feeds):** **F18–F23** (the SPA calls these endpoints), **F24** (end-to-end + `?fixture` golden payloads, 90-sec happy path).
- **Mock until ready:** the FE codes against the frozen contract + a `?fixture` payload from F17 before the engine is fully wired; F17 mocks F16 with templated copy and F15 with a green fixture until those merge.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Live API/LLM/DB flaky on stage | `?fixture` golden payload (AC4); resolver fallbacks + templated LLM copy + in-memory persist (AC7); seed offline (§15). |
| Contract churn breaks FE parallelism | F17 changes no contract; F02 is frozen. Any real gap → a reviewed F02 PR, single author (§6 program risk). |
| Secret leak via a response | No key/service-role ever serialised; CORS locked to Vite + deployed origin (AC6, §1, §11). |
| Marginals don't sum to headline | `alternatives[]` are canonical-order cumulative rungs; UI diffs them (AC2, §6.1) — no separate per-layer call to drift. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (shapes, marginals, persistence, fixture, CORS, degrade).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored — implemented to the **frozen F02 contract** (no schema change); requests/responses validate against the generated Pydantic models; no undocumented drift.
- [ ] **No secret in the frontend bundle / in any response**; no hard-coded price (prices via F12's `PricingContext`).
- [ ] Every figure traces to the engine payload or a labelled assumption (no invented precision in the wire).
- [ ] Reviewed by Lukas **and** the contract owner (Zhou owns it; Lukas signs numbers); merged to `main`; main is green.
- [ ] The demo happy-path works end-to-end (and via `?fixture`) after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §14.1 (`/recommend` + `Recommendation`/`alternatives[]`), §14.2 (`/site-check`), §2 (pipeline order), §6.1 (marginals = consecutive saving diffs), §1 (determinism `?fixture`, CORS, no-secrets), §11 (keys server-side), §14.3 (`advise_run`/`proposal` persistence), §15 (demo-safety).
- Backlog `FEATURE_BACKLOG.md` §3 E2 row F17, §4 critical path (F02→F12→F17→F24), §5 §14.1/§14.2 traceability, §2 D3.
- `specs/api/openapi.yaml` (F02 — frozen; implemented here) · F11 (engine) · F12 (resolver) · F15 (site-check) · F16 (LLM) · F04 (persistence).
