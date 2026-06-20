---
id: F23
title: Confidence chip + assumptions drawer + proposal
epic: E3 Frontend
owner: Philips
reviewers: [Lukas]
priority: P3
mvp: true
status: Ready
branch: feat/F23-confidence-proposal
depends_on: [F21]
contract_impact: reads
estimate_h: 2.5
---

# F23 — Confidence chip + assumptions drawer + proposal

> **North-Star link:** wraps the headline `monthly_saving` in honesty (a ±€ band + the biggest driver),
> lets the user **tighten the band by editing an assumption** (live re-run), explains it in plain German
> (Claude), and converts it — the green **"Apply for Cloover financing"** CTA + the proposal. It defends,
> explains, and closes the number.

## 1. Intent (what & why)

Build the trust-and-convert layer of the dashboard (§9, §7): a **confidence chip** showing `±€` with the
**biggest-driver line** (self-consumption ratio); an **assumptions drawer** listing every labelled assumption,
each **editable → triggers a live re-run** that **tightens the band** (§3.4, §7); the **Claude 3-sentence
German paragraph** explaining why this config fits this home; the **permits panel** from Site-Check; the
**"Free with the bundle" list** (smart meter, dynamic tariff, energy manager); the green **"Apply for Cloover
financing" CTA**; and a **proposal copy view (copy-to-clipboard)**. Reads `Recommendation` + `SiteCheckResponse`
from F18 state, mock-first against the §8 golden payload. **PDF export is a clearly-marked stretch.** Refs §9, §7.

## 2. Scope

**In scope**
- **Confidence chip**: `±€<`ScenarioResult.confidence.band_eur`>` (≈ **±€35** in §8/§9) + the **biggest-driver**
  line from `confidence.biggest_driver` (self-consumption ratio); the dynamic-tariff/arbitrage uncertainty noted
  as the widest, separate driver (§7).
- **Assumptions drawer**: lists **every `Recommendation.assumptions[]`** entry (`Assumption{field, value, source,
  editable}`, defaults + any overrides), each **editable** where `editable`; an edit **re-runs `/recommend`** (live)
  and the **band tightens** as the user pins down an uncertain input (§3.4, §7). Includes the **APR/term 5 %/180 mo
  TBC** assumption (D9), clearly flagged.
- **Claude German paragraph**: the **3-sentence** plain-German rationale from `Recommendation.explanation_md`
  (LLM F16) on why *this* config fits *this* home (§9).
- **Permits panel**: the Site-Check results — all green ✓ with the one real flag if present (Denkmal / street-only)
  (§4, §9), from `SiteCheckResponse.feasibility_flags`.
- **"Free with the bundle" list**: smart meter, **dynamic tariff**, Cloover energy manager (§9).
- **Green CTA "Apply for Cloover financing"** + a **proposal copy view** with **copy-to-clipboard** of the
  installer-ready proposal text (from `Recommendation.proposal_copy_md`, F16/persistence).
- Loading skeletons; empty/initial state; error fallback; accessibility for the chip, drawer, CTA, and copy action.

**Out of scope** (explicitly, to prevent creep)
- **PDF export of the proposal → 🔶 stretch** (the proposal *copy* view is the MVP; PDF is cut first if behind).
- The financing/band **math** (annuity, ±band, sensitivity, break-even) → engine **F11**; the LLM prose + proposal
  copy + number-assertion guard → **F16**; F23 only **renders + triggers re-run**.
- The hero number/curve → **F21**; buckets/scenarios/up-sell → **F22**; the four toggle rows → **F20**.
- Authoring the contract / persisting the proposal → **F02** / **F17** (`proposal` table); F23 reads them.
- Any price/subsidy computation — values arrive in the payload (§6.5, §12).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | Show a **confidence chip** `±€<`ScenarioResult.confidence.band_eur`>` + the **biggest-driver** line from `confidence.biggest_driver` (self-consumption ratio). | §7, §9 |
| R2 | Show an **assumptions drawer** listing **every `Recommendation.assumptions[]`** entry (`Assumption{field, value, source, editable}`) with its value and source. | §3.4, §7, §9 |
| R3 | Each assumption is **editable**; editing **tightens the band**. **In demo mode the edit swaps to a second committed golden fixture** (`fixtures/demo-detached-edited.json`, a tightened band) so the beat has **zero live dependency**; the live `/recommend` re-run (debounced) is the "if wifi holds" upgrade. | §3.4, §7 |
| R4 | The **APR/term 5 %/180 mo** assumption is shown as a **TBC labelled assumption (D9)**, editable; overriding it shifts/tightens the band live. | §6.5, D9 |
| R5 | Show the **Claude 3-sentence German paragraph** from `Recommendation.explanation_md` (never an FE-invented number). | §9, §1 |
| R6 | Show the **permits panel** from `SiteCheckResponse.feasibility_flags` (`FeasibilityFlag[]{product,check,status,message}`) — all green ✓ with the one real flag if present. | §4, §9 |
| R7 | Show the **"Free with the bundle" list**: smart meter, dynamic tariff, Cloover energy manager. | §9 |
| R8 | Show the green **"Apply for Cloover financing" CTA** and a **proposal copy view** with **copy-to-clipboard**. | §9 |
| R9 (🔶) | **Stretch — PDF export** of the proposal. | §9 (proposal) |

## 4. Data, formulas & sources

> No hard-coded prices. The ±band, biggest driver, break-even, the German paragraph, the permits, and the
> proposal copy all arrive in `Recommendation` / `SiteCheckResponse` / `proposal` (engine F11 + LLM F16 →
> `price_catalog` §12). F23 renders and triggers a re-run; it computes no money. This table records the read map.

| Quantity / call | Value / source | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `ScenarioResult.confidence{band_eur,low_eur,high_eur,biggest_driver}` | response field | engine F11 (§7) | `?fixture` §8 (±€35) | confidence chip |
| `Recommendation.assumptions[]` (`Assumption{field,value,source,editable}`) | response field | engine F05/F11 (§3.4, §7) | `?fixture` §8 | assumptions drawer |
| APR/term (TBC, D9) | `assumptions[]` entry (5 %/180 mo, editable) | Cloover product (§10, D9) | seeded 5 %/180 mo | drawer · financing |
| `Recommendation.explanation_md` (3 sentences) | response field (prose) | LLM F16 / Claude (§9, §1) | `?fixture` §8 | rationale paragraph |
| `SiteCheckResponse.feasibility_flags` (`FeasibilityFlag[]`) | response field | Site-Check F15 (§4) | `?fixture` §8 | permits panel |
| `Recommendation.proposal_copy_md` | response field (persisted) | LLM F16 + F17 (§14.3) | `?fixture` §8 | proposal copy view |

§7 confidence treatment, copied verbatim so F23 renders against one definition:
```
Local irradiance     → L1, ±8 % band, tightened by roof tilt/azimuth override
Dynamic tariff       → L2/L4, widest band, shown on its own line
Applicable subsidies → L3, modelled 50 %, range 30–70 % shown
Self-consumption     → L1/L2, the single biggest driver → named in the UI band
```
§9 trust/convert elements F23 reproduces faithfully:
```
Confidence chip ±€ + biggest-driver line. Assumptions drawer (editable → live re-run).
Permits panel: all green ✓, with the one real flag if present.
Free with the bundle: smart meter, dynamic tariff, Cloover energy manager.
Claude paragraph in plain German: 3 sentences on why this config fits this home.
Green CTA: Apply for Cloover financing.
```

## 5. Contract surface  *(contract_impact = reads)*

- Reads from `Recommendation`: the confidence chip from the selected `ScenarioResult.confidence{band_eur,
  low_eur, high_eur, biggest_driver}`, the assumptions drawer from `Recommendation.assumptions[]`
  (`Assumption{field, value, source, editable}`), and the Claude paragraph from `Recommendation.explanation_md`
  (proposal copy from `Recommendation.proposal_copy_md`). Reads `SiteCheckResponse{ roof_ok,
  feasibility_flags: FeasibilityFlag[], energy_context: EnergyContext, assumptions: Assumption[] }` —
  all from `specs/api/openapi.yaml` (F02).
- Editing an assumption re-issues `POST /api/v1/advisor/recommend` with the override (the F18 mutation) — the
  frozen contract already carries the override fields (the `assumptions[]` surface, `editable` per field).
- New/changed schema objects: none — F02 is frozen and carries `ScenarioResult.confidence`,
  `Recommendation.assumptions[]`, `explanation_md` and `proposal_copy_md`.
- Backwards-compatible? Yes — read + re-run via the existing endpoint.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (confidence chip — §8)** — Given the full §8 `Recommendation`, when the chip renders, then it shows
  **≈ ±€35** from `ScenarioResult.confidence.band_eur` and a biggest-driver line from `confidence.biggest_driver`
  naming the **self-consumption ratio** (§7, §9).
- [ ] **AC2 (assumptions listed)** — Given the result, when the drawer opens, then **every `Recommendation.assumptions[]`**
  entry (`Assumption{field,value,source,editable}`: consumptions, prices, autarky, KfW %, and the **APR/term TBC**)
  appears with its value and source (§3.4).
- [ ] **AC3 (edit → live re-run → band tightens)** — Given the drawer, when the user edits an assumption (e.g.
  pins roof tilt/azimuth or the autarky factor), then `/recommend` is **re-issued** with the override and the
  **±band tightens** (e.g. ±€35 → a smaller ±€) — the §3.4/§7 behaviour, demonstrated live.
- [ ] **AC3b (edit → band tightens OFFLINE via second fixture)** — Given **demo mode** with no live dependency,
  when the user edits the assumption, then the drawer **swaps to the committed `fixtures/demo-detached-edited.json`**
  (a tightened band, e.g. ±€35 → ±€22) and the chip updates with **zero** network call; the live `/recommend`
  re-run (AC3, debounced) is layered on top only "if wifi holds" — so the demo beat is deterministic offline.
- [ ] **AC4 (D9 APR/term flagged)** — Given the financing assumption, when shown, then **APR 5 % / term 180 mo**
  is labelled **TBC (D9)** and editable; changing it shifts the headline/band live (§6.5, D9).
- [ ] **AC5 (German paragraph — no invented number)** — Given the result, when the rationale renders, then it is the
  **3-sentence German** `Recommendation.explanation_md`, and any € figure in it **matches** the payload's
  `ScenarioResult` figures (the F16 number-assertion guard) — F23 invents no number (§9, §15).
- [ ] **AC6 (permits + free-with-bundle)** — Given `SiteCheckResponse`, when the permits panel renders, then it
  shows all green ✓ with the one real flag if present (e.g. Denkmal/street-only), and the **"Free with the bundle"**
  list shows smart meter, **dynamic tariff**, energy manager (§4, §9).
- [ ] **AC7 (CTA + copy-to-clipboard)** — Given the proposal view, when the user clicks **"Apply for Cloover
  financing"** the green CTA fires (records intent / routes to financing), and **copy-to-clipboard** copies the
  proposal text (`Recommendation.proposal_copy_md`) (§9).
- [ ] **AC8 (honesty/edge + a11y + states)** — Given a result where an override **widens** rather than tightens the
  band (a more uncertain value), then the band **honestly widens** (not silently clamped); the chip/drawer/CTA are
  keyboard-navigable with labels and the copy action announces success; loading shows skeletons; pre-intake shows
  the empty state; a failed re-run shows a retry-able error (not a crash). **PDF export, if built, is the 🔶 stretch
  and off by default for the demo.**

## 7. Test plan

- **Unit** (component, zero network): the chip renders `±€35` + the biggest-driver line (AC1); the drawer lists
  the assumptions incl. the D9 APR/term flag (AC2, AC4); the rationale renderer asserts the displayed € equals the
  payload (AC5, the guard); the CTA + clipboard handlers fire (AC7); an override that increases uncertainty widens
  the band (AC8).
- **Integration / contract**: with the §8 `?fixture` `Recommendation` + `SiteCheckResponse` (MSW, typed from F02),
  editing an assumption re-issues `/recommend` with the override and the band updates; the permits panel maps
  `feasibility_flags[]`; `proposal.copy_md` copies (AC3, AC6).
- **Demo-safety**: the chip, drawer, German paragraph, permits, and the CTA/proposal all render **offline** from the
  §8 golden payload (mock-first). The **"edit → band tightens" beat is offline-safe**: in demo mode the edit swaps
  to the committed **`fixtures/demo-detached-edited.json`** (tightened band) with no network (AC3b); the live
  `/recommend` re-run against `?fixture` is the "if wifi holds" upgrade (AC3, debounced).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F21** (the hero the chip attaches to), **F18** (TS client, `Recommendation`/
  `SiteCheckResponse` state, the re-run mutation, `?fixture`, loading/error/empty). Numbers/prose come from
  **F11** (band/break-even), **F15** (`SiteCheckResponse`), **F16** (German rationale + proposal copy + guard),
  **F17** (`proposal` persistence) — but F23 is **never blocked**, it reads the `?fixture` §8 payload (mock-first).
- **Downstream (feeds):** the **CTA** is the conversion endpoint of the demo (the "Generate proposal" / apply beat);
  the proposal copy is the installer-facing artifact.
- **Mock until ready:** a blocked dev mocks the band (±€35) + assumptions[] + German paragraph + `feasibility_flags[]`
  + `proposal.copy_md` from the frozen contract (§8 fixture).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| **Cloover APR/term unknown (D9)** | Shown as a **TBC labelled assumption**, editable, band updates live (AC4); one-line swap when confirmed — §16/D9. |
| LLM invents a number in the German paragraph | Render prose only; assert each € equals the payload (F16 guard); AC5 enforces it — §15. |
| Band silently understated/clamped | Edits can **widen** the band honestly (AC8); the widest (dynamic-tariff) driver stays on its own line — §7, §7.1. |
| Over-claiming permits/subsidies | Permits from `SiteCheckResponse` with the real flag surfaced; KfW/VAT/EV-grant per §6.5 (shown, not invented) — §4, §15. |
| Re-run on every keystroke thrashes the API | Debounce/commit-on-blur the assumption edit before re-issuing `/recommend`; show loading; works against `?fixture` for the demo. |
| Proposal copy/PDF scope creep | Copy-to-clipboard is MVP; **PDF export is 🔶** and off by default — Backlog row F23. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 ±€35 band, the edit→tighten re-run, and the D9 flag).
- [ ] Lint + type-check clean (`eslint` + `tsc`).
- [ ] Contract honored — reads the frozen `ScenarioResult.confidence`, `Recommendation.assumptions[]`/`explanation_md`/`proposal_copy_md` and `SiteCheckResponse`, and re-runs via the existing endpoint; no contract change needed (F02 is frozen).
- [ ] No secret added to the frontend bundle (only `VITE_API_BASE_URL`); no hard-coded price (band/financing/proposal all from the payload, §12).
- [ ] Every figure traces to the payload or a **labelled assumption** — APR/term flagged **TBC (D9)**; the German paragraph's numbers match the payload (no invented precision).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path (edit one assumption → band tightens → "Apply for Cloover financing") still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §9 (confidence chip, assumptions drawer, Claude German paragraph, permits panel, free-with-bundle, green CTA, proposal), §7/§7.1 (four certainty drivers, biggest driver, dynamic-tariff widest band), §3.4 (overrides tighten the band, live re-run), §6.5 (financing/band), §4 (Site-Check permits), §15 (LLM never invents a number), §16/D9 (APR/term TBC).
- `specs/api/openapi.yaml` (F02 — `ScenarioResult.confidence`, `Recommendation.assumptions[]`/`explanation_md`/`proposal_copy_md`, `SiteCheckResponse`) · `specs/domain/savings-engine.spec.md` (F11 band it renders).
- Backlog `FEATURE_BACKLOG.md` §3 E3 row F23 (proposal copy ✅, PDF export 🔶), §2 D9 (APR/term TBC), §5 (§9/§7/§3.4 traceability).
