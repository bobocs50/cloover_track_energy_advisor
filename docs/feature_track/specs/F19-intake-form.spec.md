---
id: F19
title: Intake form (RHF + Zod)
epic: E3 Frontend
owner: Philips
reviewers: [Lukas]
priority: P1
mvp: true
status: Ready
branch: feat/F19-intake-form
depends_on: [F18]
contract_impact: reads
estimate_h: 2.5
---

# F19 — Intake form (RHF + Zod)

> **North-Star link:** the intake collects the **first term** of the headline — current spend (elec +
> heating + mobility) — plus the physical facts (address, area, year, occupants, equipment) that let the
> engine compute `monthly_saving`. Garbage in here means a wrong number everywhere; a frictionless intake
> is what makes the 90-sec demo (§9) start with "address + 5 numbers".

## 1. Intent (what & why)

Build the React-Hook-Form + Zod intake that turns a person typing **an address and a handful of numbers**
into a valid `Household` payload for `/site-check` then `/recommend` (§3, §3.4). It enforces the mandatory
set (§3.1), exposes the existing-equipment "already owns X" inputs (§3.2), and uses **progressive
disclosure** with **labelled-assumption defaults** the user can override (overrides tighten the confidence
band, §3.4). The Zod schema mirrors the frozen contract `Household` exactly (F02) so the form can never
post a shape the backend rejects. Codes mock-first against the generated TS client. **Conversational-LLM
intake is a clearly-marked stretch.** Refs §3, §3.4.

## 2. Scope

**In scope**
- **Mandatory fields** (§3.1): `address { street, house_no, city }`, `plz` (5-digit), `floor_area_m2`,
  `building_year`, `occupants`, `electricity_eur_month`, `heating { fuel, eur_month }`,
  `mobility { kind, km_month | eur_month }`.
- **Existing-equipment inputs** (§3.2): `existing_pv_kwp`, `existing_battery_kwh`,
  `existing_heatpump_year` (nullable — null ⇒ no HP), `existing_ev`, `existing_ev_charger`.
- **Mobility km-or-€** input: either `km_month` (canonical) **or** `eur_month` per `CarType`; the form sends
  whichever the user gave (engine converts, §3.3) — `NONE` disables both.
- **Progressive disclosure**: ask the mandatory set first; reveal advanced/equipment/assumption fields on
  demand; every optional/derived field is pre-filled by a **labelled default** the user can override (§3.4).
- **Zod schema** matching the contract `Household` (required vs nullable vs optional), with inline,
  accessible validation messages; submit calls the F18 `useSiteCheck` → `useRecommend` flow.
- Loading/disabled state on submit; field-level + form-level error states; an empty/initial state.

**Out of scope** (explicitly, to prevent creep)
- **Conversational-LLM intake → 🔶 stretch** (the "one schema, two modes" §3.4 alt mode): the LLM parses
  free text into the *same* `Household`/Zod shape. Form mode is the MVP; the LLM mode is cut first if behind.
- The €→km **conversion math** → engine **F05** (the form only forwards km or €; it does not convert).
- Site-Check feasibility flags / roof check → **F15** (BE) surfaced later in **F23**'s permits panel.
- The configurator, dashboard, charts, proposal → **F20–F23**.
- Authoring/changing the contract → **F02** (this form reads it).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | **Street + house number are mandatory** (along with city, PLZ); the form blocks submit until address is complete. | §3.1, §4 |
| R2 | Collect `floor_area_m2`, `building_year`, `occupants` as required numerics with sane ranges. | §3.1 |
| R3 | Collect `electricity_eur_month` and `heating { fuel ∈ {OIL,GAS}, eur_month }` as required. | §3.1 |
| R4 | Mobility: pick `kind ∈ {PETROL,DIESEL,EV,NONE}` and enter **either** `km_month` **or** `eur_month`; `NONE` ⇒ neither required. | §3.1, §3.3 |
| R5 | Existing-equipment inputs present: `existing_pv_kwp`, `existing_battery_kwh`, `existing_heatpump_year` (**nullable**), `existing_ev`, `existing_ev_charger`. | §3.2 |
| R6 | **Progressive disclosure**: mandatory set is the default view; equipment/assumption fields are revealed on demand; result is **never blocked** on optional data (defaults fill the gap). | §3.4 |
| R7 | Every defaulted/optional field shows a **labelled assumption** and is **overridable**; an override is forwarded so it can tighten the band downstream. | §3.4, §7 |
| R8 | The **Zod schema matches the frozen `Household`** (F02): required vs nullable vs optional align field-for-field; an invalid shape cannot be submitted. | §3.1, §14.1 |
| R9 | On valid submit, call `site-check` then `recommend` via the F18 client; show loading and surface server errors with retry. | §14.2, §1 |
| R10 (🔶) | **Stretch — conversational-LLM intake**: a free-text mode parses into the *same* `Household`/Zod schema (one schema, two modes). | §3.4 |

## 4. Data, formulas & sources

> No hard-coded prices. The form collects **raw user inputs** (€/mo, km, area, year, equipment) and
> labelled-assumption **defaults only for missing optional fields**; all monetary conversions and prices
> live downstream (engine F05 + `price_catalog`, §12). This table lists the validation/disclosure inputs.

| Quantity / field | Value / rule | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `mobility.km_month` ↔ `eur_month` | one-of; km canonical | §3.3 (engine converts) | km direct | L4 · ev_kwh_year |
| `heating.fuel` enum | `OIL \| GAS` (district heating out-of-scope) | §3.2 | — | L3 · baseline |
| `mobility.kind` enum | `PETROL \| DIESEL \| EV \| NONE` | §3.1, §14.1 | NONE | L4 · case |
| `existing_heatpump_year` | nullable int; null ⇒ no HP | §3.2 | null | L3 · Case A/B select |
| Optional-field defaults | labelled assumptions, overridable | §3.4 | as labelled | §7 · confidence band |

§3.4 UX rule, copied verbatim so the form is built against one definition:
```
Progressive disclosure: ask the mandatory set, derive the rest, let power users refine. Every missing
optional field is filled by a labelled assumption the user can override (overrides tighten the
confidence band). Two intake modes, one schema: form (Zod) and conversational LLM. Never block
the result on missing data — degrade to defaults and flag uncertainty.
```

## 5. Contract surface  *(contract_impact = reads)*

- Reads the `Household` request schema from `specs/api/openapi.yaml` (F02): the mandatory set, the
  existing-equipment fields, `mobility { kind, km_month? | eur_month? }`, and the enums `FuelType`/`CarType`.
- The Zod schema is **derived from / kept in lockstep with** the generated TS `Household` type (one source
  of truth); no new fields are introduced by the form.
- New/changed schema objects: none.
- Backwards-compatible? Yes — read-only; if F02 adds a `Household` field, the Zod schema and form update in
  the same PR.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (address mandatory)** — Given the intake, when the user omits **house number** (or street/city/PLZ),
  then submit is blocked and an accessible field error appears (§3.1) — confirming address is required.
- [ ] **AC2 (mandatory numerics)** — Given missing `floor_area_m2` / `building_year` / `occupants` /
  `electricity_eur_month` / `heating.eur_month`, when submitting, then each shows a validation message and
  the form does not post (§3.1).
- [ ] **AC3 (mobility one-of)** — Given `kind=PETROL` with **only** `eur_month=160` (no km), when submitting,
  then the payload is **accepted** and posts `mobility={kind:PETROL, eur_month:160}` (km-or-€ permitted, §3.3);
  and `kind=NONE` requires neither.
- [ ] **AC4 (existing equipment + nullable HP)** — Given `existing_pv_kwp=5`, `existing_ev=true`,
  `existing_ev_charger=false`, and `existing_heatpump_year` left blank, when submitting, then the payload
  carries those values and `existing_heatpump_year: null` (⇒ no HP / fossil case, §3.2).
- [ ] **AC5 (progressive disclosure + labelled defaults)** — Given a user who fills only the mandatory set,
  when they submit, then it posts successfully (result not blocked), and each untouched optional field shows
  a **labelled default** that the user could expand and override (§3.4).
- [ ] **AC6 (override forwarded)** — Given the user overrides a labelled-assumption default, when submitting,
  then the override value is sent (so it can tighten the band downstream, §7) and is visually marked as
  user-set.
- [ ] **AC7 (contract-shape parity — §8 happy path)** — Given the §8 household (€95 elec · €180 oil · €160
  petrol · 14,800 km · detached, 3 occupants), when filled and submitted, then the Zod-validated body matches
  the frozen `Household` field-for-field and `site-check`→`recommend` are called via F18 (§14.2).
- [ ] **AC8 (honesty/edge — degrade, never block; a11y; error state)** — Given every optional field blank,
  when submitting, then the form **degrades to defaults and does not block** (§3.4); all inputs have labels,
  errors are announced (aria), keyboard-navigable; and a failing `recommend` shows a retry-able error, not a crash.

## 7. Test plan

- **Unit** (component + schema, zero network): Zod schema accepts the §8 valid household and rejects each
  missing-mandatory case (AC1–AC2); mobility one-of resolver (AC3); `existing_heatpump_year` blank → `null`
  (AC4); a defaulted field is overridable and flagged user-set (AC6).
- **Integration / contract**: with a mocked client (MSW) typed from F02, a valid submit calls `site-check`
  then `recommend`; assert the posted body matches the generated `Household` type (no extra/missing fields).
- **Demo-safety**: the §8 household fills + submits against a `?fixture` flow with **no live backend**, and
  the form renders/validates fully offline (mock-first); the stretch LLM mode, if present, is feature-flagged
  off by default for the demo.

## 8. Dependencies & interfaces

- **Upstream (needs):** **F18** (the TS client, TanStack Query mutations `useSiteCheck`/`useRecommend`,
  global loading/error/empty, `?fixture`); **F02** (the `Household` schema the Zod mirrors). Mock-first: codes
  against the generated client + a §8 fixture, never blocked on **F15/F17** (BE site-check/recommend).
- **Downstream (feeds):** the validated `Household` drives **F20** (configurator selection), **F21/F22/F23**
  (the resulting `Recommendation`). Equipment flags drive which layers F20 shows as "already installed ✓".
- **Mock until ready:** a blocked dev mocks the submit against the frozen contract — a §8 `Household` →
  golden `Recommendation` fixture (no backend).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Form posts a shape the contract rejects | Zod schema derived from / locked to the F02 `Household` type; AC7 asserts field-for-field parity. |
| Result blocked on missing optional data | §3.4 "never block — degrade to defaults and flag uncertainty"; AC8 asserts submit succeeds with defaults. |
| Existing equipment mis-entered → inflated saving | Explicit equipment inputs (§3.2) feed "already installed ✓ — no capex" in F20; nullable HP year disambiguates Case A/B. |
| Mobility €/km ambiguity | One-of input; km canonical; conversion is the engine's job (F05, §3.3) — the form forwards verbatim. |
| Stretch LLM intake bloats MVP | Conversational mode is 🔶, flagged off for the demo; form mode is the MVP path (one shared schema). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (RTL + Zod), incl. the §8 happy-path parity.
- [ ] Lint + type-check clean (`eslint` + `tsc`).
- [ ] Contract honored — Zod matches the frozen `Household`; no field drift; updated in the same PR if F02 bumps.
- [ ] No secret added to the frontend bundle (only `VITE_API_BASE_URL`); no hard-coded price (form collects raw inputs only).
- [ ] Every figure traces to a user input or a **labelled assumption** (defaults are labelled + overridable; no invented precision).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path (type address + 5 numbers → valid submit) still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §3.1 (mandatory fields), §3.2 (existing equipment + offer matrix), §3.3 (km mobility), §3.4 (progressive disclosure, two modes one schema), §4 (why address is mandatory), §7 (overrides tighten the band).
- `specs/api/openapi.yaml` (F02 — `Household`, `FuelType`, `CarType`) · `specs/domain/savings-engine.spec.md` (F05 normalisation it feeds).
- Backlog `FEATURE_BACKLOG.md` §3 E3 row F19 (conversational intake = 🔶), §5 (§3.1/§3.3/§3.4 traceability).
