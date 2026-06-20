---
id: F20
title: Configurator (4 Check24 layer rows)
epic: E3 Frontend
owner: Philips
reviewers: [Lukas]
priority: P2
mvp: true
status: Ready
branch: feat/F20-configurator-ui
depends_on: [F18]
contract_impact: reads
estimate_h: 2.5
---

# F20 — Configurator (4 Check24 layer rows)

> **North-Star link:** this is the live spine of the product — four Check24-style toggles
> (☀️🔋♨️🚗) that each recompute the single `monthly_saving` and show **what that layer adds**, with the
> per-layer "+€/mo" derived as the difference between consecutive `monthly_saving_eur` values so the rows
> **sum exactly** to the headline (§6.1). It is how the user *feels* the number move.

## 1. Intent (what & why)

Render the incremental configurator from §6/§9: four toggle rows in canonical order **☀️ Solar → 🔋 Battery
→ ♨️ Heat pump → 🚗 EV charger**, each showing **its own +€/mo and capex**. Toggling a layer recomputes the
one headline number; owned equipment renders as **"already installed ✓ — no capex"** so the saving is never
inflated (§3.2). The per-layer "+€X/mo" is the difference between consecutive `monthly_saving_eur` values in
`Recommendation.alternatives[]` — **no extra API call** (§6.1, §14.1). Offer/hidden states follow §6.3 so a
layer only appears in the states that unlock it. Codes mock-first against the §8 golden payload. Refs §6, §9.

## 2. Scope

**In scope**
- **Four layer rows in order** ☀️🔋♨️🚗 (§9 sketch), each with: emoji + label + sizing (e.g. "Solar 9 kWp"),
  its **+€/mo** contribution, its **capex** (incl. VAT/subsidy note, e.g. "€22k − €11k KfW 458"), and a toggle.
- **Per-layer +€/mo from the ladder, no extra call**: `layer_delta(n) = alternatives[n].monthly_saving_eur −
  alternatives[n-1].monthly_saving_eur` (§6.1, §14.1).
- **Owned-equipment rendering**: items the household already has show **"already installed ✓ — no capex"**
  (locked on, Δ shown as 0 / not charged) so capex is only on the delta (§3.2).
- **Toggle → recompute the single number**: toggling layers updates the headline (cumulative selection),
  reading the matching rung from `alternatives[]` (and, when à-la-carte stretch is off, snapping to the nested
  ladder rungs — the contract's 4 cumulative steps, D3).
- **Offer / hidden states** per the §6.3 matrix (Case A/B for L3/L4; hidden when Δ=0: modern HP, district
  heating, EV-with-charger, NONE, street-only parking) with a short reason.
- Loading skeleton for the rows; empty/initial (pre-intake) state; error fallback.

**Out of scope** (explicitly, to prevent creep)
- The **engine marginals / optimiser** that *produce* `alternatives[]` and the up-sell → **F10** (BE); F20
  only *reads and differences* them.
- The big hero number + honest curve → **F21**; the bucket tiles, scenario cards, and the up-sell *line* →
  **F22**; confidence/assumptions/proposal → **F23**.
- À-la-carte arbitrary subsets (any-order toggling) → 🔶 stretch (D3/§6.3); MVP is the nested ladder.
- Any pricing/subsidy computation — capex and the "− KfW/0 % VAT" figures arrive in the payload (§12, §6.5).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | Render **four rows in canonical order** ☀️ Solar → 🔋 Battery → ♨️ Heat pump → 🚗 EV charger. | §6, §9 |
| R2 | Each row shows its **own +€/mo** and its **capex** from `ScenarioResult.capex{gross_eur, subsidy_eur, after_subsidy_eur, subsidy_note}` (e.g. "€22k − €11k KfW 458", `subsidy_note` rendered). | §9 |
| R3 | The per-layer **+€/mo = consecutive difference** of `alternatives[].monthly_saving_eur` — computed in the FE, **no extra API call**. | §6.1, §14.1 |
| R4 | **Toggling a layer recomputes the single headline number** (cumulative selection) by reading the corresponding ladder rung. | §6, §6.1, §9 |
| R5 | **Owned items** render as **"already installed ✓ — no capex"** (locked, not charged), so the saving isn't inflated. | §3.2, §9 |
| R6 | **Offer/hidden** per §6.3: L1 if roof_ok & existing PV below cap; L2 if battery below recommended; L3 Case A (OIL/GAS) or Case B (old HP); L4 Case A (PETROL/DIESEL) or Case B (EV w/o charger); else hidden (Δ=0) with a reason. | §6.3, §3.2 |
| R7 | The rows **sum exactly to the headline** (canonical-order marginals); the displayed TOTAL equals the selected rung's `monthly_saving_eur`. | §6.1 |
| R8 | A row in **Case B** (HP→HP efficiency upgrade, or EV-without-charger) is labelled as such (smaller, honest saving). | §5.3, §5.4, §6.3 |

## 4. Data, formulas & sources

> No hard-coded prices. Every +€/mo and capex figure is **read from `Recommendation`** (engine F10/F11 →
> `price_catalog` §12). The FE only **differences** the ladder; it computes no money. This table records the
> read-and-difference contract.

| Quantity / call | Value / source | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `alternatives[n].monthly_saving_eur` | response field | engine F10/F11 (North Star) | `?fixture` §8 | §6.1 · per-layer +€/mo |
| `ScenarioResult.capex{gross_eur,subsidy_eur,after_subsidy_eur,subsidy_note}` | response field per rung | `price_catalog` (§12) via BE | `?fixture` §8 | §9 · capex annotation |
| Owned-equipment flags | from `Household` (F19) + payload | §3.2 | — | rows · "already installed ✓" |
| Offer/hidden state | from payload `alternatives`/`upsell` + flags | §6.3 | — | rows · visibility |

§6.1 marginal identity, copied verbatim so the FE differences against one definition:
```
state₀ = baseline (minus any already-owned equipment, §3.2)
for each layer added in order L1→L2→L3→L4 (skipping already-owned):
    Δ_net(layer) = monthly_saving(stateₙ) − monthly_saving(stateₙ₋₁)   # what THIS layer adds
    cumulative_net = Σ Δ_net = monthly_saving (North Star) for the current selection
```
and the per-layer value the FE derives **with no extra call** (§14.1):
```
layer_delta_eur_month(n) = alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur
```

## 5. Contract surface  *(contract_impact = reads)*

- Reads `Recommendation { best, alternatives[], upsell }` and per-rung `ScenarioResult.monthly_saving_eur`
  (the per-layer +€/mo is the consecutive diff of these) / `breakdown` / `installment_eur_month` /
  `capex{gross_eur,subsidy_eur,after_subsidy_eur,subsidy_note}` from `specs/api/openapi.yaml` (F02).
  `alternatives[]` = the **four cumulative ladder steps** (☀️→🔋→♨️→🚗).
- Reads the `Household` existing-equipment flags (F19/F02) to drive "already installed ✓" rows.
- New/changed schema objects: none (read-only). À-la-carte `selection{}` is only used if the stretch mode is on.
- Backwards-compatible? Yes — read-only; tracks F02.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (order + four rows)** — Given the §8 `Recommendation`, when the configurator renders, then exactly
  four rows appear in order **☀️ 🔋 ♨️ 🚗**, each showing a +€/mo and a capex (§9).
- [ ] **AC2 (per-layer deltas — §8, no extra call)** — Given `alternatives[].monthly_saving_eur =
  [-24, -24, -4, +120]` (the §8 cumulative-net column), when the FE differences them, then the rows show
  **−€24 (☀️), ≈ €0 (🔋), +€20 (♨️), +€124 (🚗)** (the §8 Δ-net column) and **no second network request** is made.
- [ ] **AC3 (sum = headline)** — Given those rows, when the full bundle is selected, then the displayed TOTAL
  equals `alternatives[3].monthly_saving_eur` = **+€120/mo** (rows sum exactly to the headline, §6.1).
- [ ] **AC4 (toggle recomputes)** — Given the full ladder, when the user un-ticks ♨️ and 🚗, then the headline
  snaps to the battery rung's `monthly_saving_eur` (≈ the §8 −€24 cumulative) by reading `alternatives[1]` — no
  recompute in the bundle (§6, §6.1).
- [ ] **AC5 (owned equipment — no capex)** — Given `existing_pv_kwp` already at/above the recommendation, when
  the ☀️ row renders, then it shows **"already installed ✓ — no capex"**, is locked on, and contributes **no
  capex** to any total (§3.2) — the saving is not inflated.
- [ ] **AC6 (offer/hidden — §6.3)** — Given heating `GAS`, the ♨️ row is **offered (Case A)**; given a modern HP
  it is **hidden (Δ=0)**; given `existing_ev ∧ ¬existing_ev_charger` the 🚗 row is **offered (Case B — add wallbox)**;
  given an EV that already has a charger (or `NONE`, or street-only parking) the 🚗 row is **hidden** with a reason.
- [ ] **AC7 (honesty/edge — ≈€0 battery shown honestly)** — Given the §8 battery rung, when 🔋 is toggled on, then
  its row reads **≈ €0/mo** (not hidden, not floored to a fake positive) with the honest note that it pays off as
  load grows (§8.1) — the awkward number is shown truthfully.
- [ ] **AC8 (a11y + states)** — Given the configurator, when navigated by keyboard/screen-reader, then each toggle
  is a labelled, focus-visible control announcing its +€/mo and state; loading shows row skeletons; pre-intake
  shows the empty state; a payload error shows a retry-able fallback (not a crash).

## 7. Test plan

- **Unit** (component + pure differ, zero network): the consecutive-difference util maps
  `[-24,-24,-4,+120] → [-24, 0, +20, +124]` (AC2); the TOTAL equals the selected rung (AC3); owned-equipment
  rows render "already installed ✓ — no capex" and contribute zero capex (AC5); offer/hidden resolver over the
  §6.3 matrix (AC6).
- **Integration / contract**: with a `?fixture` §8 `Recommendation` (MSW, typed from F02), toggling rows reads
  the right `alternatives[]` rung and never issues a second request; field names match the contract.
- **Demo-safety**: full row interaction works **offline** against the §8 golden payload (mock-first); the ≈€0
  battery and the Case-B labels render deterministically for the demo.

## 8. Dependencies & interfaces

- **Upstream (needs):** **F18** (TS client, TanStack Query `Recommendation` state, `?fixture`, loading/error/empty);
  **F19** (the `Household` + equipment flags); the payload shape from **F02**. The numbers come from **F10/F11**
  (BE) but F20 is **never blocked** — it differences the `?fixture` §8 `alternatives[]` (mock-first).
- **Downstream (feeds):** the current selection + per-layer deltas feed **F21** (hero total + curve), **F22**
  (buckets, scenario cards, up-sell line), **F23** (proposal reflects the chosen rung).
- **Mock until ready:** a blocked dev mocks `alternatives[]` from the frozen contract (the §8 vector
  `[-24,-24,-4,+120]`) and differences it locally.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Rows don't sum to the headline (trust killer) | Use the **canonical-order consecutive difference** (§6.1); AC3 asserts TOTAL = selected rung; never recompute in the FE. |
| Owned equipment inflates the saving | "already installed ✓ — no capex", locked, zero capex (§3.2); AC5 guards it. |
| Battery ≈€0 looks like a bug | Show it **honestly** with the "pays off as load grows" note (§8.1); AC7 asserts it isn't hidden/floored. |
| A layer offered in the wrong state | Drive visibility from the §6.3 matrix + equipment flags; AC6 covers Case A/B and all hidden cases. |
| Extra API calls per toggle | Per-layer +€/mo is a pure difference of `alternatives[]` — **no extra call** (§14.1); AC2 asserts zero second request. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 `[-24,-24,-4,+120] → [-24,0,+20,+124]` vector).
- [ ] Lint + type-check clean (`eslint` + `tsc`).
- [ ] Contract honored — reads `Recommendation.alternatives[]`/`ScenarioResult` as frozen; no payload drift; no extra calls.
- [ ] No secret added to the frontend bundle (only `VITE_API_BASE_URL`); no hard-coded price (capex/+€ all from the payload, §12).
- [ ] Every figure traces to the payload or a labelled assumption — the configurator differences, it does not invent.
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path (toggle 🔋 ≈€0 → toggle ♨️+🚗 the number jumps) still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §6 (configurator), §6.1 (marginals sum to headline), §6.3 (dependency & toggle/offer matrix), §3.2 (existing equipment, "already installed ✓"), §8/§8.1 (worked example, battery ≈€0), §9 (dashboard sketch), §14.1 (per-layer = consecutive difference, no extra call).
- `specs/api/openapi.yaml` (F02 — `Recommendation`, `alternatives[]`, `ScenarioResult`) · `specs/domain/savings-engine.spec.md` (F10 marginals it reads).
- Backlog `FEATURE_BACKLOG.md` §3 E3 row F20, §2 D3 (nested ladder = MVP, à-la-carte = 🔶), §5 (§6.1/§6.3 traceability).
