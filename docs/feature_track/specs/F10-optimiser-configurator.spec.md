---
id: F10
title: Configurator marginals + optimiser + up-sell
epic: E1 Domain Core
owner: Lukas
reviewers: [Zhou]
priority: P3
mvp: true
status: Ready
branch: feat/F10-optimiser-configurator
depends_on: [F06, F07, F08, F09]
contract_impact: reads
estimate_h: 2
---

# F10 — Configurator marginals + optimiser + up-sell

> **North-Star link:** this is where the headline is assembled — `cumulative_net = Σ Δ_net =
> monthly_saving`. It produces the per-layer "+€X/mo" rows, picks the rung that **maximises**
> `monthly_saving`, and frames the up-sell, all from the four layer modules (§6.1–§6.4).

## 1. Intent (what & why)

F10 walks the strict nested ladder L1→L2→L3→L4 on the **running state** (each layer re-evaluated with
everything ticked below it), computing each layer's marginal contribution so that the canonical-order
marginals **sum exactly to the headline** `monthly_saving` (§6.1). It then runs the optimiser to return
the rung with the **largest `monthly_saving`** — not necessarily the deepest — and emits the up-sell diff
versus the next-smaller rung (§6.4). It also applies the §6.3 dependency/toggle rules so each layer is
offered only in the right state (owned / modern-HP / EV+charger / street-only ⇒ Δ = 0, hidden).

## 2. Scope

**In scope**
- Marginal math per §6.1: `Δ_gross` on the running state, `Δ_capex` (delta only), `Δ_installment` (annuity on the delta), `Δ_net`, `cumulative_net`.
- The exact-sum invariant: `Σ Δ_net == monthly_saving` of the deepest selected rung (every toggle row honest).
- The optimiser `recommend()`: pick the rung with **max `monthly_saving`**, skipping a layer whose installment outweighs its saving.
- Up-sell = the diff (Δ monthly_saving + the "why" framing) vs the next-smaller rung.
- §6.3 offer/toggle gating: which layers are offered vs hidden (Δ = 0) by household state.
- Producing the four cumulative ladder rungs that map to contract `alternatives[]` (§14.1).

**Out of scope** (explicitly, to prevent creep)
- The annuity/subsidy/break-even/confidence-band internals → **F11** (§6.5, §7); F10 calls into the financing/annuity primitive but does not own KfW/VAT/band logic.
- À-la-carte arbitrary subsets (≤16 evaluations) → 🔶 stretch (§6.3); MVP is the nested ladder (D3).
- LLM prose for the up-sell sentence → **F16** (§9); F10 emits the structured up-sell data only.
- The layer physics themselves → F06/F07/F08/F09; F10 only orchestrates and diffs them.

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | Start from `state₀ = baseline` minus any already-owned equipment (§3.2), then add layers in order L1→L2→L3→L4, skipping already-owned. | §6.1, §3.2 |
| R2 | For each layer: `Δ_gross = gross_saving(stateₙ) − gross_saving(stateₙ₋₁)` (computed on the running state). | §6.1 |
| R3 | `Δ_capex = capex_after_subsidy(layer)` on the **delta only**; `Δ_installment = annuity(Δ_capex, annual_rate, term_months)`. | §6.1 |
| R4 | `Δ_net = Δ_gross − Δ_installment`; `cumulative_net = Σ Δ_net = monthly_saving` for the current selection. | §6.1 |
| R5 | **Invariant:** canonical-order marginals sum **exactly** to the headline `monthly_saving` (no residual). | §6.1 |
| R6 | `recommend()` returns the rung with the **largest `monthly_saving`** (not necessarily the deepest); a layer whose installment outweighs its saving is skipped. | §6.4 |
| R7 | Up-sell = a diff vs the next-smaller rung (Δ monthly_saving + the displaced-cost reason), surfaced inline. | §6.4 |
| R8 | Apply §6.3 offer rules: L1 (roof_ok + PV below cap), L2 (battery below recommended), L3 (Case A OIL/GAS or Case B old HP; hidden for modern HP/district heat), L4 (Case A petrol/diesel or Case B EV-no-charger; hidden for EV+charger, NONE, street-only). Hidden ⇒ Δ = 0. | §6.3 |
| R9 | Later layers raise `annual_consumption_kwh`, re-lifting L1/L2 self-consumption on the running state (this is why a bigger upgrade can raise the saving). | §6.2 |
| R10 | Emit the four cumulative rungs as the ladder feeding contract `alternatives[]`; the per-layer "+€X/mo" = difference between consecutive `monthly_saving` values (no extra call). | §14.1 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> No prices here are hard-coded — capex/€-per-kWh come from `price_catalog` (§12) via `PricingContext`
> through the layer modules. This feature owns the **orchestration formula**, not constants.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `Δ_capex` (per layer, delta only) | from `price_catalog` §12 via `PricingContext` | §12 (Destatis/market) | seeded §12 values | §6.1 · Δ_capex |
| `annuity(...)` | annuity primitive (provided by F11) | §6.5 | — | §6.1 · Δ_installment |
| Financing APR / term | **5 % / 180 mo — TBC (D9), labelled assumption** | Cloover product (§6.5, §10) | 5 % / 180 mo seeded | §6.1 · Δ_installment |
| Layer Δ_gross | from F06/F07/F08/F09 on the running state | §5.1–§5.4 | layer fallbacks | §6.1 · Δ_gross |

Key formula(s), copied verbatim from §6.1 so the implementer codes against one definition:
```
state₀ = baseline (minus any already-owned equipment, §3.2)
for each layer added in order L1→L2→L3→L4 (skipping already-owned):
    stateₙ = stateₙ₋₁ + layer
    Δ_gross(layer)       = gross_saving(stateₙ) − gross_saving(stateₙ₋₁)   # on the running state
    Δ_capex(layer)       = capex_after_subsidy(layer)        # from price_catalog (§12), only the delta
    Δ_installment(layer) = annuity(Δ_capex, annual_rate, term_months)
    Δ_net(layer)         = Δ_gross − Δ_installment           # what THIS layer adds to the saving
    cumulative_net       = Σ Δ_net   = monthly_saving (North Star) for the current selection
```
Optimiser & up-sell (§6.4): `recommend()` walks the ladder and returns the rung with the **largest
`monthly_saving`** (not necessarily the deepest — a layer whose installment outweighs its saving is
skipped). Up-sell = a diff vs the next-smaller rung, surfaced inline (e.g. *"Going from PV+battery
(−€24/mo) to the full bundle lands +€120/mo — because you're still burning oil + petrol that the heat
pump and EV displace."*). Canonical-order marginals **sum exactly** to the headline → every toggle row is honest.

## 5. Contract surface  *(if contract_impact ≠ none)*

- **Reads only** — `contract_impact: reads`. Produces the four cumulative ladder rungs that populate `Recommendation.alternatives[]` and `best`; the per-layer "+€X/mo" is the difference between consecutive `ScenarioResult.monthly_saving_eur` (§14.1) — no new field, no extra call.
- New/changed schema objects: none. Up-sell maps to the existing `Recommendation.upsell` field (§14.1).
- Backwards-compatible? Yes — orchestrates existing layer outputs into the frozen `Recommendation`/`alternatives[]` shape; reads only.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (exact-sum invariant, §6.1/§8 — EXACT, DD-1-independent)** — Given the §8 ladder, when the per-layer Δ net values are summed, then `Σ Δ_net == monthly_saving` of the full rung **exactly**, with **zero residual**. This is the canonical exact-equality test and holds under either DD-1 accounting model (F03 §0): the headline (≈ +€120/mo) and the sum are identical regardless of how PV self-consumption is attributed across buckets. Compute the headline **as** `Σ Δ_net`, never independently.
- [ ] **AC2 (cumulative rungs, §8 — ILLUSTRATIVE pending DD-1)** — Given the §8 home, when the ladder is walked, then assert **structure/signs** (Solar mildly negative, Battery ≈ break-even, HP positive, EV largest positive, cumulative-now positive, after-payoff ≫ now) and **magnitude within ±15 %** of the §8 illustrative figures (cumulative now ≈ −€24 / −€24 / −€4 / +€120; after payoff ≈ €80 / €124 / €230 / €364; note the after-payoff running sum is €231 ±€1 by exact addition). The per-rung euro split is DD-1-dependent and **captured from the engine fixture (F24), not hand-pinned**; only AC1's exact-sum is euro-exact.
- [ ] **AC3 (optimiser picks max, not deepest, §6.4)** — Given a configuration where adding a layer makes `monthly_saving` decrease (installment > its saving), when `recommend()` runs, then it returns the rung with the **largest** `monthly_saving`, skipping that layer — not automatically the deepest.
- [ ] **AC4 (optimiser on §8 — ILLUSTRATIVE pending DD-1)** — Given the §8 home where the full bundle is the max, when `recommend()` runs, then `best` = the full ladder, which **lands at the absolute destination ≈ +€120/mo now** (illustrative, ±15 %, DD-1-dependent), and the up-sell vs the PV+battery rung is reported as a **diff = `headline − PV+battery cumulative_net`** (e.g. ≈ +€120 − (−€24) ≈ +€144/mo, computed from the rungs — **not a hard-pinned constant**) with the oil+petrol-displaced reason. Assert the destination and that the up-sell equals the computed rung difference; do not pin €144 as an independent literal.
- [ ] **AC5 (running-state lift, §6.2)** — Given Layers 3–4 added (≈7,400 kWh new load), when L1/L2 are re-evaluated on the running state, then their self-consumption value rises (a deeper rung can raise the saving) — assert L1/L2 Δ_gross is higher post-HP/EV than at the bare battery rung.
- [ ] **AC6 (toggle/offer gating, §6.3)** — Given owned equipment (existing PV at cap / modern HP / EV+charger / street-only parking), when the ladder is built, then those layers are **hidden with Δ = 0** and excluded from the sum (saving never inflated by owned hardware).
- [ ] **AC7 (honesty/edge — delta-only capex)** — Given `existing_battery_kwh > 0` below recommended, when Layer 2 is evaluated, then `Δ_capex` is on the **added delta only** (not the total), and the rung's net reflects that smaller installment.

## 7. Test plan

- **Unit** (pure domain only, zero I/O): the full §8 ladder as a fixture vector asserting the **exact sum** (`Σ Δ_net == monthly_saving`, zero residual — the one euro-exact assertion) and the per-rung **structure/signs + magnitude ±15 %** (illustrative pending DD-1, captured from the engine fixture not hand-pinned); optimiser-picks-max case (a constructed rung where a layer is net-negative and gets skipped); the up-sell diff computed as `headline − PV+battery cumulative` (≈ +€144/mo, derived from the rungs, not a literal); running-state lift (L1/L2 Δ_gross higher after HP/EV); offer-gating matrix (owned/modern-HP/street-only ⇒ Δ 0); delta-only capex for existing battery.
- **Integration / contract**: assert the four rungs serialise into `alternatives[]` with monotone-or-as-expected `monthly_saving_eur`, `best` is the max rung, and `upsell` is populated (against the frozen F02 contract shapes).
- **Demo-safety**: deterministic with a seeded `PricingContext` + the D9 default APR/term; `?fixture` golden payload reproduces the §8 rungs exactly; no I/O in the orchestration.

## 8. Dependencies & interfaces

- **Upstream (needs):** F06 (L1), F07 (L2), F08 (L3, both cases + `kfw_case`), F09 (L4, both cases) — each returning a gross bucket on the running state and a `Δ_capex` (delta); the F11 `annuity(...)` primitive for `Δ_installment`; F05 baseline + existing-equipment folding; F03 §8 test vectors.
- **Downstream (feeds):** F11 (financing overlay wraps the chosen rung with KfW/VAT/break-even/confidence), F17 (`/recommend` serialises `best`/`alternatives[]`/`upsell`), F22 (UI scenario cards + up-sell line).
- **Mock until ready:** before F11's annuity exists, mock `annuity()` with the D9 default (5 %/180 mo) closed-form; blocked consumers mock the four §8 rungs from the frozen contract.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Marginals don't sum to the headline (rounding) | Assert the exact-sum invariant as a test (AC1, exact equality, DD-1-independent); compute the headline as `Σ Δ_net`, never independently — §6.1. |
| **Per-rung €/mo double-counts PV self-consumption (DD-1)** | The §8 cumulative-rung figures are **illustrative ±15 %** until DD-1 (F03 §0) is resolved; the up-sell is a **computed rung difference**, not a pinned €144; only the exact-sum invariant (AC1) and signs are euro-exact. The headline is unchanged by DD-1. |
| Optimiser returns the deepest rung by habit | Explicit max-over-rungs selection (AC3) with a net-negative-layer fixture; never "deepest = best" — §6.4. |
| Owned equipment inflates the saving | §6.3 gating ⇒ owned/modern-HP/EV+charger/street-only set Δ = 0 and are excluded from the sum (AC6) — §15. |
| À-la-carte scope creep | MVP = nested ladder (D3); à-la-carte is a flagged 🔶 stretch behind the same pure evaluator. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 **exact-sum** vector and optimiser vectors; per-rung €/mo asserted as structure + ±15 % illustrative pending DD-1).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored (reads only; rungs → `alternatives[]`/`best`/`upsell`); no payload drift.
- [ ] No secret added to the frontend bundle; no hard-coded price (capex via `PricingContext`).
- [ ] Every figure traces to a §10/§12 source or a labelled assumption (D9 APR/term flagged; §8 per-rung figures illustrative pending DD-1, F03 §0).
- [ ] Reviewed by **Zhou** (independent, per frontmatter — contract-touching domain feature owned by Lukas); merged to `main`; main is green.
- [ ] The demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §6.1, §6.2, §6.3, §6.4, §3.2, §8, §14.1
- `specs/api/openapi.yaml` (`Recommendation`, `ScenarioResult`, `alternatives[]`, `upsell`) · `specs/domain/savings-engine.spec.md` (§8 vectors via F03)
