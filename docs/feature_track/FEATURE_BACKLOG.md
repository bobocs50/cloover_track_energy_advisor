# Feature Backlog — Heimwende Energy Advisor (Cloover track)

> **Canonical source of truth for feature IDs, owners, dependencies and MVP scope.**
> Derived 1:1 from [`system_workflow.md`](../design_plan/system_workflow.md) v0.3.1. If this file and a
> per-feature spec disagree on ID/owner/dep, **this file wins** — fix the spec.
> Deadline **Sun 2026-06-21 14:00**. North Star: `monthly_saving = current_spend − (installment + new_energy_cost)`.

Legend — **Owner:** 🟦 Zhou (backend/adapters/contract) · 🟩 Lukas (domain engine, data verification, review) · 🟪 Philips (frontend/UX).
**MVP:** ✅ must work in the demo · 🔶 stretch (cut first if behind).
**Pri = build phase**, mapped to [`TIMELINE.md`](./TIMELINE.md) milestones (start **Sat 18:00**, deadline **Sun 14:00**, last 3 h = video/submission):
**P0**→H+2 (Sat 20:00 foundation) · **P1**→H+5 (Sat 23:00 slice) · **P2**→H+8 (Sun 02:00 four layers) · **P3**→H+10 (Sun 04:00 MVP) · **P4**→H+17 (Sun 11:00 integration/freeze) · **P5**→H+17–20 (video + submission).

---

## 1. Team & ownership model

| Person | Primary surface | Owns features | Also |
|--------|-----------------|---------------|------|
| **Lukas** 🟩 | **Pure domain core** (`apps/api/src/app/domain/`) + **data-source verification** + the §10/§12 reference values | F03, F05–F11 | **Reviews every PR** (review gate); signs off all numbers/sources |
| **Zhou** 🟦 | **Backend BFF**: FastAPI, adapters, Supabase, the OpenAPI contract, persistence, fixtures | F01, F02, F04, F12–F17, F24(be) | Owns contract changes |
| **Philips** 🟪 | **Frontend**: Vite SPA, intake, configurator, dashboard, charts, proposal | F18–F23, F24(fe) | Owns demo UX feel |

> Split rationale: **domain math (Lukas) ⟂ backend plumbing (Zhou) ⟂ UI (Philips)** are three nearly
> non-overlapping surfaces. The **frozen contract (F02)** is the seam that lets all three run in
> parallel from P0 onward. F03 (domain spec) lets Lukas TDD while Zhou wires adapters against mocks.

## 2. Locked decisions (from system_workflow.md §16 — resolved so nobody re-litigates)

| # | Decision | Choice | Note |
|---|----------|--------|------|
| D1 | Market scope | **Germany only** | all data is DE; do not generalise for the demo |
| D2 | Frontend stack | **Vite + React + TS + Tailwind SPA** | **clear the stale Next.js `.next/` artifacts (F01)**; FastAPI is the only server |
| D3 | Configurator mode | **Nested ladder = MVP**; à-la-carte subsets = 🔶 | the 4 cumulative rungs are the contract `alternatives[]` |
| D4 | KfW grant default | **50 %** (base 30 % + Klima 20 %) for fossil→HP; **30 %** for HP→HP | editable; range 30–70 % shown (§6.5) |
| D5 | Self-consumption fidelity | **Heuristic load-aware autarky = MVP**; 8760-h sim = 🔶 | §5.1, §8.1 |
| D6 | Dynamic tariff in demo | **Seeded €0.12/kWh net spread = MVP**; live SMARD = visible 🔶 toggle | §7.1 |
| D7 | Denkmal / permits | **OSM + national checkbox**; Bavaria live WFS = 🔶 | §4 |
| D8 | LLM provider | **Claude default**, provider-agnostic adapter | OpenAI fallback (§1) |
| ⚠️ **D9** | **Financing APR / term** | **DEFAULT 5 % / 180 mo — TBC: confirm Cloover's real product** | the one genuine unknown; flagged in UI + F11 spec. **Ask a Cloover mentor early.** |

## 3. Epics → features (the breakdown)

### E0 — Foundations & Contract  *(P0, unblocks everyone — do these first)*

| ID | Feature | Owner | MVP | Pri | depends_on | system_workflow.md |
|----|---------|:-----:|:---:|:---:|------------|--------------------|
| **F01** | Monorepo scaffold & toolchain — Vite SPA + FastAPI(uv) + ruff/mypy/pytest + vitest + env hygiene; **remove stale `.next/`** | 🟦 | ✅ | P0 | — | §1 |
| **F02** | **Freeze `specs/api/openapi.yaml`** + generate TS client + FastAPI Pydantic models | 🟦 (rev 🟩) | ✅ | P0 | F01 | §14, §3, §6 |
| **F03** | **`specs/domain/savings-engine.spec.md`** — formalise §5–§8 math + the §8 worked example as TDD test vectors | 🟩 (rev 🟦) | ✅ | P0 | — | §5–§8, §10 |
| **F04** | Supabase schema + seed: `reference_plz`, **`price_catalog`**, cache tables, `advise_run`, `proposal`, `denkmal_seed`, `mastr_seed` — offline-safe | 🟦+🟩 | ✅ | P0→P1 | F01 | §12, §14.3, §10 |

### E1 — Pure Domain Core  *(Lukas · TDD, zero I/O · the credibility)*

| ID | Feature | Owner | MVP | Pri | depends_on | system_workflow.md |
|----|---------|:-----:|:---:|:---:|------------|--------------------|
| **F05** | Intake normalisation & baseline — €→**km** mobility, existing-equipment ("already owns X") folding, labelled assumptions, current_monthly_spend | 🟩 | ✅ | P1 | F03 | §3.1–§3.4 |
| **F06** | **Layer 1 — Solar/PV**: load-aware self-consumption, feed-in 7.78 ct, existing-PV delta, PVGIS-shaped yield input | 🟩 | ✅ | P1 | F05 | §5.1 |
| **F07** | **Layer 2 — Battery**: extra self-consumption + dynamic-tariff arbitrage, no double-count, ≈€0 honesty | 🟩 | ✅ | P2 | F06 | §5.2, §8.1 |
| **F08** | **Layer 3 — Heat pump**: Case A fossil→HP, Case B old-HP→efficiency upgrade, SCOP, PV overlap, KfW nuance | 🟩 | ✅ | P2 | F05 | §5.3, §3.2 |
| **F09** | **Layer 4 — EV charger**: Case A petrol→EV, Case B EV-without-charger (charging-cost swap), blended price, street-only fallback | 🟩 | ✅ | P2 | F05 | §5.4, §3.2 |
| **F10** | **Configurator marginals + optimiser + up-sell** — cumulative ladder sums exactly to headline; pick max-net rung; up-sell diff | 🟩 | ✅ | P3 | F06,F07,F08,F09 | §6.1–§6.4 |
| **F11** | **Financing overlay + confidence** — annuity, KfW 458, 0 % VAT, break-even month, ±band + biggest-driver, sensitivity | 🟩 | ✅ | P3 | F10 | §6.5, §7 |

### E2 — Backend Adapters & Services  *(Zhou · all I/O lives here)*

| ID | Feature | Owner | MVP | Pri | depends_on | system_workflow.md |
|----|---------|:-----:|:---:|:---:|------------|--------------------|
| **F12** | **Resolver** — PLZ→lat/lon/retail/grid-fee; reads `price_catalog` → builds `PricingContext` injected into the engine | 🟦 | ✅ | P1 | F04 | §11, §12, §2 |
| **F13** | **PVGIS adapter** — `PVcalc` live + cache (TTL 30d) + constant-980 fallback | 🟦 | 🔶 (fallback is ✅) | P2 | F12 | §5.1, §11, §14.3 |
| **F14** | **Dynamic-tariff adapter** — SMARD/aWATTar pull + cache (TTL 1d) + seeded €0.12 spread | 🟦 | 🔶 (seed is ✅) | P2 | F04 | §7.1, §11 |
| **F15** | **Site-Check adapter** — permits/feasibility flags, OSM parking, Denkmal checkbox, MaStR neighbour-count seed | 🟦 | ✅ (lite) | P2 | F12 | §4, §14.2 |
| **F16** | **LLM advisor adapter** — Claude prose-only (rationale + up-sell + installer proposal copy) + **number-assertion guard** | 🟦 | ✅ | P3 | F02 | §1, §9, §15 |
| **F17** | **API endpoints** `/recommend` + `/site-check` — wire resolver→engine→persistence; `?fixture` determinism | 🟦 | ✅ | P3 (F17a skeleton→P1) | F02,F11,F12 | §14.1, §14.2 |

### E3 — Frontend  *(Philips · Vite SPA, mock-first against the frozen contract)*

| ID | Feature | Owner | MVP | Pri | depends_on | system_workflow.md |
|----|---------|:-----:|:---:|:---:|------------|--------------------|
| **F18** | App shell + generated TS client + state (TanStack Query) + API integration & loading/error/fixture | 🟪 | ✅ | P1 | F02 | §1, §9 |
| **F19** | **Intake** — RHF + Zod form, progressive disclosure, existing-equipment inputs; conversational-LLM intake = 🔶 | 🟪 | ✅ | P1 | F18 | §3, §3.4 |
| **F20** | **Configurator** — 4 Check24-style layer rows, toggles, per-layer +€/mo & capex, "already installed ✓" states | 🟪 | ✅ | P2 | F18 | §6, §9 |
| **F21** | **Dashboard hero** — the big €/month number, **honest two-phase curve chart** + break-even, before/after | 🟪 | ✅ | P2 | F18 | §9 |
| **F22** | Bucket breakdown (elec/heat/mobility) + scenario comparison cards + inline up-sell line | 🟪 | ✅ | P3 | F20,F21 | §9, §6.4 |
| **F23** | Confidence chip + **assumptions drawer (live re-run)** + Claude paragraph + proposal view + green CTA | 🟪 | ✅ (proposal copy 🔶 PDF) | P3 | F21 | §9 |

### E4 — Integration, Demo & Submission  *(shared)*

| ID | Feature | Owner | MVP | Pri | depends_on | system_workflow.md |
|----|---------|:-----:|:---:|:---:|------------|--------------------|
| **F24** | **End-to-end integration + demo determinism** — wire FE↔BE, seed offline, `?fixture` golden payloads, 90-sec happy path green | 🟦+🟪 (rev 🟩) | ✅ | P4 | F17,F22 | §9, §15 |
| **F25** | **Submission pack** — README (setup/run), 2-min Loom demo, pitch deck (5 slides), public repo, API/tooling docs | All | ✅ | P5 | F24 | HACKATHON_MANUAL §Submission |

**Counts:** 25 features · **MVP-critical: 23** · **2 stretch features** (F13, F14 — both have ✅ MVP fallbacks already shipping in F06/F04/F07) · **2 stretch sub-scopes** (conversational intake in F19, PDF export in F23).

## 4. Dependency graph (critical path in **bold**)

```
        ┌─────────────────────────── P0 ───────────────────────────┐
        │  F01 scaffold ──► F02 contract ◄── (parallel) F03 spec    │
        │       └──► F04 supabase/price_catalog                     │
        └───────────────────────────────────────────────────────────┘
              │                 │                      │
   ┌──────────┴─────┐   ┌───────┴────────┐    ┌────────┴─────────┐
   │ DOMAIN (Lukas) │   │ BACKEND (Zhou) │    │ FRONTEND (Philips)│
   │ **F05►F06►F07**│   │ F12 resolver   │    │ F18 shell ►F19    │
   │ F08, F09 ──┐   │   │ F13 pvgis      │    │ F20 configurator  │
   │ **►F10►F11**│  │   │ F14 dynprice   │    │ F21 hero/curve    │
   │            │   │   │ F15 site-check │    │ F22 ►F23          │
   └────────────┼───┘   │ F16 llm        │    └─────────┬─────────┘
                │       │ **►F17 endpoints**◄───────────┘
                └───────────────┴──────────► **F24 integration** ──► **F25 submit**
```

**Longest path (drives the deadline):** F01 → F02 → F12 → F17 → F24 → F25, run alongside
F03 → F05 → F06 → F10 → F11 (engine) → F17. Protect these; everything else has slack or a fallback.

## 5. Traceability — every `system_workflow.md` section maps to a feature (proves nothing is dropped)

| §  | Topic | Feature(s) |
|----|-------|-----------|
| §1 | Tech stack, no-secrets, BFF, determinism | F01, F02, F18, F24 |
| §2 | End-to-end pipeline | F12→F17 (be), F05–F11 (engine), F24 |
| §3.1 | Mandatory intake fields | F05, F19, F02 |
| §3.2 | Existing-equipment paths + offer matrix | F05, F08, F09, F20 |
| §3.3 | Mobility km-based €→km | F05, F19 |
| §3.4 | Progressive-disclosure UX | F19, F23 |
| §4 | Site-Check permits/obligations | F15, F23 |
| §5.1 | Layer 1 Solar | F06, F13 |
| §5.2 | Layer 2 Battery | F07, F14 |
| §5.3 | Layer 3 Heat pump (Case A/B) | F08 |
| §5.4 | Layer 4 EV charger (Case A/B) | F09 |
| §6.1 | Marginal math sums to headline | F10 |
| §6.2 | Cumulative interaction (why bigger=bigger saving) | F10 (engine), F22 (UI proof) |
| §6.3 | Dependency & toggle rules | F10, F20 |
| §6.4 | Optimiser & up-sell | F10, F22 |
| §6.5 | Financing overlay + subsidies (KfW/VAT/BAFA) | F11, F04 |
| §7 | Savings certainty (4 drivers) | F11 (band), F13 (irradiance), F14 (tariff), F08/§7 subsidies |
| §7.1 | Dynamic-tariff model | F14, F07, F09 |
| §8 / §8.1 | Worked example + battery ≈€0 derivation | F03 (vectors), F07, F10 |
| §9 | Dashboard / live configurator | F20, F21, F22, F23 |
| §10 | Reference dataset (constants + "used in") | F03, F04, F12 |
| §11 | Data sources (PVGIS/SMARD/OSM/Denkmal/MaStR/KfW/Anthropic) | F12, F13, F14, F15, F16 |
| §12 | `price_catalog` DB-driven pricing | F04, F12 |
| §13 | Resource lists (comprehensive + optimal) | F04, F12, F13, F14 (selection realised) |
| §14.1 | `/recommend` contract | F02, F17 |
| §14.2 | `/site-check` contract | F02, F15, F17 |
| §14.3 | Supabase schema | F04 |
| §15 | Risks & demo-safety | F24 (+ enforced as invariants, PROCESS §4) |
| §16 | Open decisions | resolved in §2 above (D1–D9) |

> **Verification:** §1–§16 all map to ≥1 feature → the backlog is **complete** with respect to the plan.
> Any new requirement must be added here **and** get a feature ID before code is written.

## 6. Risks carried at the program level (feature-level risks live in each spec)

| Risk | Owner | Mitigation |
|------|-------|-----------|
| **Stale Next.js scaffold** contradicts the Vite decision (D2) | Zhou | F01 deletes `apps/web/.next/`; rebuild as Vite; CI has no Next.js |
| **Cloover APR/term unknown (D9)** | Lukas | default 5 %/180 mo, **labelled assumption** in UI + spec; ask a mentor in P0; one-line swap if confirmed |
| Contract churn after P0 blocks parallelism | Zhou | freeze F02 in P0; later changes are reviewed PRs that bump the client same-commit |
| Self-consumption ratio not credible → number doubted | Lukas | load-aware autarky (F06/F07), show band (F11), cite source; §8.1 transparent derivation |
| **§8 double-counts PV self-consumption** — L1/L2 credit total-load self-consumption *and* L3 `solar_covered` / L4 €0.20-blend credit the same PV→load energy again | Lukas | **resolve F03 DD-1** (one credit locus; recommended: credit in L1/L2, price L3/L4 at grid/off-peak). §8 figures are **illustrative ±15%**; the demo fixture is captured from the engine; per-layer marginals still sum **exactly** to the headline |
| **Engine is a ~15.5h serial single-owner chain (Lukas)** colliding with his review + number-audit at freeze | Lukas/All | review gate scoped to engine/number PRs (PROCESS §3); **F08/F09 depend only on F05 → pair a 2nd dev on them** if behind; run the number-audit ~Sun 10:00, before the 11:00 freeze |
| Live API flaky on stage | Zhou | seed everything (F04); PVGIS/SMARD are toggles; `?fixture` golden payloads (F24) |
| LLM invents a number | Zhou | LLM prose-only + number-assertion guard (F16); PROCESS §4.1 |
| Overnight throughput drop / scope creep | All | MVP marked per feature; cut stretch at phase gates (TIMELINE); sleep in shifts |
| Integration left to the end | Zhou+Philips | mock-first from the frozen contract; F24 starts as soon as F17 returns a fixture |

## 7. How to read this with the other docs

- **What to build & why** → `../design_plan/system_workflow.md` (the blueprint, v0.3.1).
- **How/when each person works** → [`TIMELINE.md`](./TIMELINE.md) (phases P0–P5 + swimlanes).
- **The process & gates** → [`PROCESS.md`](./PROCESS.md).
- **Each feature's detail** → [`specs/Fxx-*.spec.md`](./specs/) (one per row above, from `_TEMPLATE.spec.md`).
- **Status at a glance** → [`README.md`](./README.md) board.
