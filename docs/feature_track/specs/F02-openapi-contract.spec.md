---
id: F02
title: Freeze OpenAPI contract + TS client
epic: E0 Foundations
owner: Zhou
reviewers: [Lukas]
priority: P0
mvp: true
status: Ready
branch: feat/F02-openapi-contract
depends_on: [F01]
contract_impact: extends
estimate_h: 1.5
---

# F02 — Freeze OpenAPI contract + TS client

> **North-Star link:** The contract *is* the carrier of the headline: every `ScenarioResult` exposes
> `monthly_saving_eur`, and the four-rung `alternatives[]` ladder is exactly how the configurator
> derives each layer's "+€X/mo". Freezing it is what lets domain, backend, and frontend build the
> number in parallel (Backlog §1).

## 1. Intent (what & why)

Author and **freeze** `specs/api/openapi.yaml` defining the two endpoints — `POST /api/v1/advisor/recommend`
and `POST /api/v1/advisor/site-check` — and all request/response schemas, then generate the TypeScript
client (openapi-typescript or equivalent) and the FastAPI Pydantic models from it. This is the **seam
that unblocks all parallel work** (Backlog §1, §6): FE codes against the generated client, BE implements
the schema, the domain engine (F05–F11) targets the response shapes. Implements §14.1/§14.2 with the
§3 intake fields and §6 ladder semantics. Refs §14, §3.1–§3.3, §6.

## 2. Scope

**In scope**
- `specs/api/openapi.yaml` defining `POST /api/v1/advisor/recommend` and `POST /api/v1/advisor/site-check` (§14.1, §14.2).
- Request schema `Household` with the full mandatory + existing-equipment + à-la-carte field set (see §4 / §5 below; §3.1, §3.2, §14.1).
- Response schemas `Recommendation` (incl. `current_monthly_spend_eur`, LLM `explanation_md`/`proposal_copy_md`, `assumptions[]`) and `ScenarioResult` (incl. `capex`, `confidence`, `saving_after_payoff_eur`, `break_even_month`) (§14.1, §9, §7).
- `site-check` response `{ roof_ok, feasibility_flags[], energy_context, assumptions[] }` with fully-typed leaf objects (§14.2).
- Generated **TS client** (openapi-typescript or similar) committed for FE; generated/authored **Pydantic models** for BE.
- The `?fixture=<id>` query param on `/recommend` for demo determinism (§1) declared in the contract.

**Out of scope** (explicitly, to prevent creep)
- Endpoint *implementation* / wiring resolver→engine→persistence → **F17**.
- The domain math behind the numbers → **F03** (spec) and F05–F11 (engine).
- Supabase tables → **F04**. LLM prose generation → **F16**.
- À-la-carte *evaluation* logic (the `selection{}` field is declared here as optional, but its engine support is a stretch per D3/§6.3).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | `POST /api/v1/advisor/recommend` accepts a `Household` and returns `Recommendation`. | §14.1 |
| R2 | `POST /api/v1/advisor/site-check` accepts the address (+ `floor_area_m2`/`building_year`) and returns `{ roof_ok, feasibility_flags[], energy_context, assumptions[] }`. | §14.2 |
| R3 | `Recommendation` = `{ best: ScenarioResult, alternatives: ScenarioResult[], upsell }`; `alternatives[]` carries the **four cumulative ladder steps** (☀️→🔋→♨️→🚗). | §14.1, §6.1 |
| R4 | `ScenarioResult` carries `breakdown { electricity_eur_month, heating_eur_month, mobility_eur_month }`, `installment_eur_month`, `monthly_saving_eur`, `payback_note`. | §14.1 |
| R11 | `Recommendation` also carries `current_monthly_spend_eur` (baseline for before/after), `explanation_md` + `proposal_copy_md` (LLM prose — never the numeric authority, F16), and `assumptions[]`. Consumed by F21 (before/after), F23 (drawer + Claude paragraph), F16 (copy). | §9, §7, §14.1 |
| R12 | `ScenarioResult` also carries `capex { gross_eur, subsidy_eur, after_subsidy_eur, subsidy_note }` (F20 capex column), `saving_after_payoff_eur` + `break_even_month` (F21 honest curve), and `confidence { band_eur, low_eur, high_eur, biggest_driver }` (F11/F21/F23 ±band). | §6.5, §7, §9 |
| R13 | `upsell` is `Upsell { from_scenario_id, to_scenario_id, delta_eur_month, reason_md }` (F22); `assumptions[]` items are `Assumption { field, value, source, editable }` (F23 drawer). | §6.4, §9 |
| R5 | `Household.address` is `{ street, house_no, city }` and **mandatory** (street + house number required). | §3.1, §14.1 |
| R6 | `Household` includes `floor_area_m2`, `building_year`, `occupants`, `electricity_eur_month`, `heating { fuel, eur_month }`, `mobility { kind, km_month \| eur_month }`. | §3.1, §3.3, §14.1 |
| R7 | `Household` includes existing-equipment fields: `existing_pv_kwp`, `existing_battery_kwh`, `existing_heatpump_year` (**nullable** — null ⇒ no HP), `existing_ev: bool`, `existing_ev_charger: bool`. | §3.2, §14.1 |
| R8 | Optional à-la-carte `selection { pv, battery, heat_pump, ev }` of booleans is declared (stretch evaluation). | §6.3, §14.1 |
| R9 | The generated TS client and FastAPI Pydantic models are produced from this single `openapi.yaml` (one source of truth). | §1 (contract row) |
| R10 | `/recommend` declares an optional `fixture` query param returning a frozen payload for the demo. | §1 (determinism) |

## 4. Data, formulas & sources

> The contract carries *fields*, not numbers — every monetary value flows through at runtime from
> `price_catalog` (§12) via the resolver. F02 invents no prices.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `feedin_per_kwh` (declared as a result, not a constant) | flows in payload | Bundesnetzagentur (€0.0778) | — | L1 · feed-in revenue (computed downstream) |
| `monthly_saving_eur` | response field | derived by engine (F11) | — | North Star · headline |
| `mobility.km_month` ↔ `eur_month` | request field (km canonical) | §3.3 conversion (engine) | km direct | L4 · ev_kwh_year |

The contract enforces the **North-Star identity** as the meaning of `monthly_saving_eur`:
```
monthly_saving = current_monthly_spend − (loan_installment + new_energy_cost)
```
and the **per-layer marginal** the FE derives without an extra call (§14.1, §6.1):
```
layer_delta_eur_month(n) = alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur
```

## 5. Contract surface  *(contract_impact: extends)*

- **Request/response fields touched in `specs/api/openapi.yaml`:** the full surface is authored here.
- **New/changed schema objects:**
  - `Household` — **exact field set (the seam — list in full):**
    `address { street: str, house_no: str, city: str }` (required) · `plz: str` · `floor_area_m2: int` · `building_year: int` · `occupants: int` · `electricity_eur_month: number` · `heating { fuel: FuelType, eur_month: number }` · `mobility { kind: CarType, km_month?: number, eur_month?: number }` · `existing_pv_kwp: number` (default 0) · `existing_battery_kwh: number` (default 0) · `existing_heatpump_year: int | null` · `existing_ev: bool` · `existing_ev_charger: bool` · `selection?: { pv: bool, battery: bool, heat_pump: bool, ev: bool }` (optional, à-la-carte stretch).
  - `FuelType` enum: `OIL | GAS` (district heating noted out-of-scope, §3.2). `CarType` enum includes `PETROL | DIESEL | EV | NONE` (`EV` already in scope, §14.1).
  - `Recommendation { best: ScenarioResult, alternatives: ScenarioResult[], upsell: Upsell, current_monthly_spend_eur: number, explanation_md: str, proposal_copy_md: str, assumptions: Assumption[] }`.
    `explanation_md`/`proposal_copy_md` are LLM prose (F16) — **never the numeric source of truth**; every € in them must also appear in a `ScenarioResult` (F16 guard).
  - `ScenarioResult { scenario_id: str, label: str, breakdown { electricity_eur_month, heating_eur_month, mobility_eur_month }, capex: Capex, installment_eur_month: number, monthly_saving_eur: number, saving_after_payoff_eur: number, break_even_month: int, confidence: Confidence, payback_note: str }`.
  - `Capex { gross_eur: number, subsidy_eur: number, after_subsidy_eur: number, subsidy_note: str }` — e.g. note `"€22k − 50% KfW 458"` (F20 capex column).
  - `Confidence { band_eur: number, low_eur: number, high_eur: number, biggest_driver: str }` — the `±band` + biggest-driver line (F11/F21/F23; §7).
  - `Upsell { from_scenario_id: str, to_scenario_id: str, delta_eur_month: number, reason_md: str }` (§6.4 diff vs next-smaller rung).
  - `Assumption { field: str, value: str, source: str, editable: bool }` — drives the assumptions drawer; `editable:true` rows re-run on change (F23, §7).
  - `SiteCheckResponse { roof_ok: bool, feasibility_flags: FeasibilityFlag[], energy_context: EnergyContext, assumptions: Assumption[] }`.
  - `FeasibilityFlag { product: str, check: str, status: "green"|"amber"|"info", message: str }` — the §4 permit/obligation rows (🟢/🟡/ℹ️).
  - `EnergyContext { lat: number, lon: number, specific_yield_kwh_per_kwp: number, retail_price_eur_kwh: number, grid_fee_eur_kwh: number, climate_zone: str, mastr_neighbour_count: int | null }`.
- **Backwards-compatible?** This is the *initial freeze* (extends from F01's empty layout). It is the baseline; any later change is a reviewed PR that bumps the TS client in the same commit (Backlog §6).

> **Labelled assumption:** `plz` is carried on `Household` alongside `address` because §3.1 lists Postcode
> as its own mandatory field (irradiance/grid-fee/prices). §14 names the response fields but not their
> leaf types; the concrete shapes above (`Upsell`, `Capex`, `Confidence`, `Assumption`, `FeasibilityFlag`,
> `EnergyContext`) are the **authored, frozen** types — they were completed so that **no downstream
> consumer (F11/F15/F16/F20/F21/F22/F23) needs a later contract bump** to read the band, capex, after-payoff,
> LLM prose, or assumptions. This closes the contract; later changes are deliberate reviewed PRs (Backlog §6).

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1** — Given `openapi.yaml`, when linted/validated (e.g. `openapi` validator), then it is a valid OpenAPI doc with both paths `/api/v1/advisor/recommend` and `/api/v1/advisor/site-check`.
- [ ] **AC2** — Given the `Household` schema, when inspected, then `address.street`, `address.house_no`, `address.city`, `floor_area_m2`, `building_year`, `occupants`, `electricity_eur_month`, `heating`, `mobility` are all required, and `existing_heatpump_year` is nullable.
- [ ] **AC3** — Given `Recommendation`, when validated against a sample payload with 4 `alternatives`, then each element is a `ScenarioResult` carrying all of `breakdown{electricity,heating,mobility}_eur_month`, `capex{gross,subsidy,after_subsidy,note}`, `installment_eur_month`, `monthly_saving_eur`, `saving_after_payoff_eur`, `break_even_month`, `confidence{band_eur,low_eur,high_eur,biggest_driver}`, `payback_note`.
- [ ] **AC4** — Given the contract, when the TS client and Pydantic models are generated, then both compile (`tsc` / `mypy`) and expose `Household`, `Recommendation`, `ScenarioResult`, `SiteCheckResponse`.
- [ ] **AC5 (per-layer marginal identity)** — Given any `alternatives[]`, when the FE derives layer deltas as consecutive differences of `monthly_saving_eur`, then it equals the per-layer Δ-net — no extra call (§6.1). *Illustrative fixture:* cumulative `[-24, -24, -4, +120]` ⇒ deltas `[-24, 0, +20, +124]`. The identity is exact for **any** values; the specific numbers are illustrative (§8, pending F03 DD-1).
- [ ] **AC6 (honesty/edge)** — Given a `Household` with `mobility.km_month` omitted but `eur_month` present (or `existing_heatpump_year: null`), when validated, then the payload is accepted (km-or-€ is permitted; null HP ⇒ no heat pump), not rejected.
- [ ] **AC7 (LLM-prose + assumptions carried)** — Given a `Recommendation`, when inspected, then `current_monthly_spend_eur`, `explanation_md`, `proposal_copy_md` and `assumptions[]` (each `{field,value,source,editable}`) are present — so F21/F23/F16 read them from the payload, never a side channel.
- [ ] **AC8 (site-check fully typed)** — Given a `SiteCheckResponse`, when validated, then `feasibility_flags[]` are `FeasibilityFlag{product,check,status,message}` and `energy_context` is a typed `EnergyContext` (not a free-form object) — F15/F23 code against concrete types.

## 7. Test plan

- **Unit** (schema, zero I/O): validate `openapi.yaml`; round-trip the §8 sample `Recommendation` payload through the Pydantic models and the TS types.
- **Integration / contract**: assert the generated client and Pydantic models agree on field names/required-ness for `Household`/`ScenarioResult`; assert the consecutive-difference identity in AC5 against a fixture.
- **Demo-safety**: declare and exercise the `?fixture=<id>` param shape so F24 can return golden payloads (§1, §15).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F01** (the `apps/` layout + tooling to host the spec, client, and models).
- **Downstream (feeds):** **everyone** — F05–F11 (engine targets `ScenarioResult`), F17 (implements the endpoints), F18 (FE uses the TS client), F16 (asserts LLM copy matches `monthly_saving_eur`). Backlog §1, §4.
- **Mock until ready:** consumers mock against the frozen contract — a fixture `Recommendation` payload generated from `openapi.yaml` (the §8 vector is the canonical fixture).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Contract churn after P0 blocks parallelism | Freeze in P0; later changes are reviewed PRs that bump the client in the same commit (Backlog §6). |
| FE/BE drift from the contract | One source of truth (`openapi.yaml`) generates *both* the TS client and Pydantic models (R9, AC4). |
| Field set incomplete → engine can't model an edge case | §4/§5 lists the **exact** field set incl. existing-equipment + nullable HP year; AC2 guards it (§3.2, §14.1). |
| Leaf shapes under-specified → consumers blocked / late contract bump | **Closed:** `Upsell`, `Capex`, `Confidence`, `Assumption`, `FeasibilityFlag`, `EnergyContext` are fully typed in §5; AC7/AC8 guard them. No consumer (F11/F15/F16/F20–F23) needs a later bump. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests.
- [ ] Lint + type-check clean (generated Pydantic `mypy`-clean; generated TS client `tsc`-clean).
- [ ] Contract honored — `openapi.yaml` authored/frozen in this PR (`extends`); TS client + Pydantic models regenerated in the same commit.
- [ ] No secret added to the frontend bundle; no hard-coded price (the contract carries fields, not prices — §12).
- [ ] Every figure traces to a source or a labelled assumption (the `plz` placement + leaf shapes are labelled assumptions; §8 numbers cite §8).
- [ ] Reviewed by Lukas **as the contract owner** (`contract_impact ≠ none`); merged to `main`; main is green.
- [ ] The demo happy-path (a fixture `Recommendation` deserialises in FE + BE) still works after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §14.1 (`/recommend`), §14.2 (`/site-check`), §3.1–§3.3 (intake fields, km mobility), §6.1 (marginal ladder), §1 (contract row + determinism).
- `specs/api/openapi.yaml` — the artifact authored by this feature.
- Backlog `FEATURE_BACKLOG.md` §1 (contract is the parallelism seam), §6 (contract-freeze risk), §3 E0 row F02.
