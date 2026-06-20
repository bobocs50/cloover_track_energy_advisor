---
id: F03
title: Domain math spec + worked-example test vectors
epic: E0 Foundations
owner: Lukas
reviewers: [Zhou]
priority: P0
mvp: true
status: Ready
branch: feat/F03-domain-spec
depends_on: []
contract_impact: none
estimate_h: 2
---

# F03 — Domain math spec + worked-example test vectors

> **North-Star link:** This file *defines* the headline. It formalises every formula that produces
> `monthly_saving = current_spend − (installment + new_energy_cost)` and pins the §8 worked example as
> named test vectors the pure engine (F05–F11) is TDD'd against — so the number is correct by
> construction, not by accident.

## 0. ⚠️ OPEN DESIGN DECISION — DD-1: Single-credit accounting for PV self-consumption of electrified load (must resolve before coding L3/L4)

> **Status: OPEN — blocks the L3/L4 per-bucket vectors. The headline `monthly_saving` is unaffected
> (it is `Σ Δ_net` either way); only the *attribution* between buckets changes.**

**The bug this prevents.** The PV self-consumption of the heat-pump and EV load must be credited in
**exactly one place**. Today it is credited **twice**:

- (a) L1/L2 already compute `self_consumed_kwh = autarky × annual_consumption_kwh` where
  `annual_consumption_kwh = base + HP_elec + EV_kwh` (§5.1) — so the running-state self-consumption
  uplift of the HP/EV load is *already* in the electricity bucket; **and**
- (b) L3 *also* credits `solar_covered_kwh` (PV→HP, §5.3) in the heating bucket, **and** L4's €0.20
  home-blend *also* bakes in free PV surplus (PV→EV, §5.4).

The PV→load energy is therefore double-counted, which inflates some per-bucket figures and makes the
§8 hand-pinned per-bucket vectors (esp. HP +€107, EV +€133) **unsatisfiable** by a consistent engine.

**RECOMMENDED model (consistent single-credit).** Credit the PV self-consumption of **all** load
(`base + HP + EV`) in **L1/L2 on the running state**; **L3 prices HP grid electricity** and **L4 prices
EV charging at the off-peak/grid price WITHOUT a separate free-PV credit** (i.e. L3 `overlap → 0` /
L4 `home_blended_price → the off-peak grid blend, no PV share` *for attribution purposes*). The §6.2
"a bigger upgrade lifts the value of the installed PV" story then lives entirely in L1/L2 and **nothing
is double-counted**. Under this model the honest EV rung is ≈ **+€115/mo gross** (fuel €159.7 − home
charge €44.4) and the heating bucket alone ≈ **€77/mo**, with the ~€30/mo of extra PV self-consumption
they unlock appearing in the re-evaluated L1/L2 electricity bucket — not a second time in L3/L4.

**Alternative model (equally valid if applied consistently).** Credit the PV self-consumption in
**L3/L4** (keep `solar_covered` and the PV-share in the €0.20 blend), and run **L1/L2 autarky on the
*base* load only** so the HP/EV load does not also lift the electricity bucket. Either model is
correct; **mixing them (today's state) is the bug.**

**Invariant that holds under both models.** The chosen model changes only the per-bucket attribution.
The engine's `monthly_saving = Σ Δ_net` (§6.1) remains **the single source of truth** and is identical
under either model; the marginals-sum-to-headline equality (AC3) is an exact test regardless of DD-1.

**Until DD-1 is resolved**, the §8 per-bucket €/mo figures (Solar −€24, Battery ≈€0, HP +€20, EV +€124,
cumulative +€120) are treated as **ILLUSTRATIVE** (structure + sign + magnitude within tolerance), not
euro-exact golden vectors — see AC2. The reproducible intermediate quantities (base load, HP elec, EV
kWh, PV self-consumption, feed-in rate, annuities, the §8.1 battery sub-derivation) are **unaffected by
DD-1 and stay exact** (AC4–AC6).

## 1. Intent (what & why)

Author `specs/domain/savings-engine.spec.md`: the single mathematical contract for the pure domain core.
It formalises the four-layer math of §5, the §6.1 marginals, §6.5 financing, and §7 confidence, and turns
the §8 worked example (and the §8.1 battery sub-derivation) into **named, machine-checkable test vectors**.
The engine (F05–F11) is implemented test-first against these vectors; F03 contains no code, only the
definitions and fixtures. Refs §5–§8, §10. **See §0 (DD-1): the §8 *per-bucket* €/mo figures are
illustrative (structure + sign + magnitude-within-tolerance) until the single-credit accounting for PV
self-consumption is resolved; the reproducible intermediates and the marginals-sum-to-headline invariant
stay exact.**

## 2. Scope

**In scope**
- Formalise Layer 1–4 formulas verbatim from §5.1–§5.4 (load-aware self-consumption, battery self-cons + arbitrage, HP Case A/B with SCOP, EV Case A/B with blended price).
- The §6.1 marginal ladder (`Δ_gross`/`Δ_capex`/`Δ_installment`/`Δ_net`, canonical-order summation), §6.5 financing (annuity, KfW 458, 0 % VAT, break-even), §7 confidence band + drivers.
- Named test vectors from §8 (per-step ladder table) and §8.1 (battery sub-derivation), with the §8 derived physical quantities as inputs.
- Definition of the `PricingContext` shape the engine receives (prices **injected**, never imported — §12).

**Out of scope** (explicitly, to prevent creep)
- Implementing the engine modules → **F05–F11** (this spec is their TDD target).
- Fetching any data (PVGIS/SMARD) → adapters **F12–F15**.
- Seeding `price_catalog` rows → **F04** (this spec *consumes* those values as injected inputs).
- The OpenAPI shapes → **F02** (this spec maps onto `ScenarioResult`, doesn't redefine it).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | Specify Layer 1 (Solar): load-aware `self_consumed_kwh = autarky_factor × annual_consumption_kwh` (capped ≤ yield), feed-in at €0.0778, existing-PV credits only incremental yield. | §5.1 |
| R2 | Specify Layer 2 (Battery): extra self-consumption (autarky 0.30→~0.60, net of lost feed-in) + dynamic-tariff arbitrage (`total_kwh × cycles × round_trip × spread`), no double-count. | §5.2, §8.1 |
| R3 | Specify Layer 3 (Heat pump) **Case A** (fossil→HP) and **Case B** (old-HP efficiency upgrade): heat demand, `hp_electricity = heat_demand / new_SCOP`, PV overlap, baseline replaced, KfW nuance. | §5.3, §3.2 |
| R4 | Specify Layer 4 (EV charger) **Case A** (petrol→EV) and **Case B** (EV-no-charger charging swap): `ev_kwh_year = km_year × 18/100`, `home_blended_price ≈ €0.20`, public €0.45 baseline (Case B). | §5.4, §3.2 |
| R5 | Specify §6.1 marginals computed **on the running state** in canonical order L1→L2→L3→L4 (skipping owned), summing **exactly** to the headline. | §6.1 |
| R6 | Specify §6.5 financing: `capex_after_subsidy`, `annuity(...)`, KfW 458 (50 % Case A / 30 % Case B), 0 % VAT PV/battery, EV grant €0, break-even month. | §6.5 |
| R7 | Specify §7 confidence: the four drivers (irradiance ±8 %, dynamic-tariff widest band, subsidies 30–70 %, self-consumption named) and how the ±band is produced. | §7, §7.1 |
| R8 | Encode the §8 worked example as named test vectors: the **per-step €/mo are ILLUSTRATIVE** (assert structure/signs + magnitude within ±15 %, pending DD-1, §0); only the AC3 marginals-sum-to-headline equality is euro-exact. The canonical demo figures are captured from the engine fixture (F24), not hand-pinned. | §8, §0 |
| R9 | Encode the §8.1 battery sub-derivation as a named vector (+€529/yr = +€44/mo gross, NET ≈ €0). | §8.1 |
| R10 | Define `PricingContext` (prices injected, engine stays pure — no price imported). | §12 |

## 4. Data, formulas & sources

> Physics/policy constants below come from §10; **every monetary price is injected via `PricingContext`
> from `price_catalog` (§12)** — the spec references them by name, never hard-codes them.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| Specific PV yield (DE) | live per lat/lon | PVGIS (EU JRC) | const **980** kWh/kWp | L1 · annual_yield |
| Self-consumption autarky | 0.30 PV-only · ~0.60 +batt | BSW/HTW Berlin | as stated | L1, L2 · self_consumed |
| Retail electricity price | `price_catalog` (€0.37) | Destatis/BNetzA | seeded | L1–L4 · import & displaced cost |
| Feed-in (≤10 kWp) | `price_catalog` (€0.0778) | Bundesnetzagentur | seeded | L1 · feed-in revenue |
| Dynamic-tariff spread (net) | €0.12/kWh (seeded; live toggle) | SMARD/EPEX | seeded €0.12 | L2 arbitrage · L4 EV sched |
| Battery cycles · round-trip | 300 · 0.90 | engineering/datasheets | as stated | L2 · arbitrage |
| Heat pump SCOP — new | 3.5 (Case A) … 4.0 (Case B target) | manufacturer JAZ/BWP | as stated | L3 · hp_electricity |
| Heat pump SCOP — old (Case B) | 2.8 (age ≥12yr/pre-2014) | BWP/field data | as stated | L3 Case B · old baseline |
| PV→HP overlap | 0.15 PV-only · 0.30 +batt | engineering | as stated | L3 · solar_covered |
| EV consumption | 18 kWh/100 km | class default | as stated | L4 · ev_kwh_year |
| EV home blended charge | €0.20/kWh | derived (PV+off-peak+public) | as stated | L4 · home_charge_cost |
| EV public charge | `price_catalog` (€0.45) | CPO avg (Destatis) | seeded | L4 Case B · public baseline |
| KfW 458 grant | 50 % Case A / 30 % Case B (range 30–70 %) | KfW (official) | as stated | §6.5 · L3 capex |
| Financing APR · term | **5 % · 180 mo — LABELLED ASSUMPTION (D9, Cloover real TBC)** | Cloover product (TBC) | 5 %/180 mo | §6.5 · annuity |

Key formula(s), copied verbatim from the spec:
```
# North Star (§6.5)
monthly_saving = gross_saving − installment          # = current_spend − (installment + new_energy_cost)
saving_after_payoff = gross_saving ;  break_even_month = first month cumulative_net ≥ 0

# §6.1 marginal ladder (on the running state, canonical order, sums exactly to headline)
for layer in [L1,L2,L3,L4] (skip already-owned):
    Δ_gross(layer)       = gross_saving(stateₙ) − gross_saving(stateₙ₋₁)
    Δ_capex(layer)       = capex_after_subsidy(layer)            # from price_catalog, delta only
    Δ_installment(layer) = annuity(Δ_capex, annual_rate, term_months)
    Δ_net(layer)         = Δ_gross − Δ_installment
    cumulative_net       = Σ Δ_net = monthly_saving

# L1 (§5.1)
self_consumed_kwh = autarky_factor × annual_consumption_kwh          # capped ≤ annual_yield
elec_saving_self  = self_consumed_kwh × retail_price
elec_feedin_rev   = (annual_yield_kwh − self_consumed_kwh) × 0.0778
L1_bucket_eur_mo  = (elec_saving_self + elec_feedin_rev) / 12

# L2 (§5.2)
extra_self_value = (autarky_with_batt − autarky_pv_only) × annual_consumption_kwh × (retail_price − 0.0778)
arbitrage_value  = total_kwh × cycles_per_year × round_trip × dynamic_spread
L2_bucket_eur_mo += (extra_self_value + arbitrage_value) / 12

# L3 (§5.3)  Case B efficiency driver = heat_demand × (1/old_SCOP − 1/new_SCOP) × retail_price
hp_electricity_kwh = heat_demand_kwh / new_SCOP ; annual_consumption_kwh += hp_electricity_kwh
hp_grid_kwh = hp_electricity_kwh − hp_electricity_kwh × overlap
L3_bucket_eur_mo = baseline_heating_cost − hp_grid_kwh × retail_price / 12

# L4 (§5.4)
ev_kwh_year = km_year × ev_consumption_kwh_per_100km / 100 ; annual_consumption_kwh += ev_kwh_year
L4_bucket_eur_mo = baseline_mobility_cost/12 − ev_kwh_year × home_blended_price / 12
```

## 5. Contract surface

`contract_impact: none`. F03 defines the math behind the `ScenarioResult` fields that **F02** owns; it
introduces no new request/response field. (It documents how the engine populates
`breakdown{electricity,heating,mobility}_eur_month`, `installment_eur_month`, `monthly_saving_eur`,
`payback_note` — but the schema itself lives in `openapi.yaml`.)

## 6. Acceptance criteria (testable — these become the tests)

> The §8 inputs (named **`V_WORKED_BASE`**): detached DE home, 3 people · €95 elec · €180 oil · €160 petrol
> ⇒ **baseline €435/mo**; PV 9 kWp · battery 8 kWh · air-source HP · wallbox; financing 180 mo @ 5 %.
> Derived physical quantities: base load **3,081** kWh/yr · HP elec **4,769** kWh/yr · EV **2,664** kWh/yr
> (14,800 km × 18/100) · PV yield **8,820** kWh/yr.

- [ ] **AC1 (baseline vector `V_WORKED_BASE`)** — Given the §8 inputs, when the baseline is computed, then `current_monthly_spend = €435/mo` (95 + 180 + 160).
- [ ] **AC2 (ladder vector `V_WORKED_LADDER` — ILLUSTRATIVE, pending DD-1)** — Given `V_WORKED_BASE`, when the four layers are added in order, then the ladder asserts **(i) structure/signs**: Solar mildly **negative** (small base load, cheap feed-in), Battery **≈ break-even**, Heat pump **positive**, EV the **largest positive**, **cumulative net now positive**, and **after-payoff ≫ now**; **(ii) magnitude within tolerance** of the §8 illustrative figures (per-step Δ net ≈ `☀️ −€24`, `🔋 ≈ €0`, `♨️ +€20`, `🚗 +€124`; cumulative now ≈ `−€24, −€24, −€4, +€120`; after payoff ≈ `€80, €124, €230, €364`) at **±15 %, illustrative pending DD-1 — the canonical demo numbers are captured from the engine fixture (F24), not hand-pinned**. The exact per-step euro split depends on the DD-1 accounting choice; only the structure, signs and the AC3 exact-sum invariant are euro-exact. (Source disclaimer, §8: "Illustrative; the TDD'd engine produces the exact figures.")
- [ ] **AC3 (marginals sum exactly — EXACT, DD-1-independent)** — Given `V_WORKED_LADDER`, when the four Δ-net values are summed, then they equal the final headline `monthly_saving` **exactly** (`Σ Δ_net == monthly_saving`, zero residual, §6.1). This is an **exact equality test** and holds under either DD-1 model (the headline ≈ +€120/mo is the same; only the per-bucket attribution shifts).
- [ ] **AC4 (battery sub-derivation vector `V_BATTERY_8KWH`)** — Given base load 3,081 kWh/yr at the battery rung, when §8.1 is computed, then `(a) +€342/yr, (b) −€72/yr, (c) +€259/yr ⇒ gross +€529/yr = +€44/mo`, installment `−€44/mo`, **NET ≈ €0/mo** (±€1).
- [ ] **AC5 (financing vector)** — Given capex after subsidy per step (`☀️ €13,050 @ 0 % VAT`, `🔋 €5,600`, `♨️ €11,000 = €22k − 50 % KfW`, `🚗 €1,200`) at 180 mo @ 5 %, when annuity is applied, then installments = `€103, €44, €87, €10` (±€1).
- [ ] **AC6 (honesty/edge — battery ≈€0 + owned equipment)** — Given the battery rung in isolation (no HP/EV load yet), when computed, then its Δ net is **≈ €0 (not −€20)** per §8.1; and given `existing_pv_kwp > 0` (or `existing_battery_kwh > 0`), then the vector charges capex **only on the delta** and credits only incremental yield (§3.2) — no double-count.

## 7. Test plan

- **Unit** (pure domain only, zero I/O): the named vectors above (`V_WORKED_BASE`, `V_WORKED_LADDER`, `V_BATTERY_8KWH`, financing vector) become the canonical fixtures F05–F11 are TDD'd against; each layer formula in §4 has a direct assertion.
- **Integration / contract**: assert the vector's `breakdown`/`monthly_saving_eur` shape maps onto `ScenarioResult` (F02) so the engine output is contract-valid.
- **Demo-safety**: the §8 ladder vector doubles as the `?fixture` golden payload basis (F24) — the canonical demo numbers are **captured from the engine fixture, not hand-pinned** (the per-bucket split is illustrative pending DD-1, §0); the AC3 exact-sum invariant and AC4–AC6 reproducible intermediates hold precisely.

## 8. Dependencies & interfaces

- **Upstream (needs):** nothing (`depends_on: []`); authored in parallel with F02 in P0 (Backlog §4).
- **Downstream (feeds):** **F05–F11** (the entire pure engine TDDs against these vectors), **F07/F10** (battery ≈€0 + marginal-sum), **F02** (maps onto `ScenarioResult`), **F24** (golden fixture). Backlog §1, §5 (§8/§8.1 row).
- **Mock until ready:** consumers need nothing mocked — F03 *is* the spec; F04's `price_catalog` values appear here as injected `PricingContext` inputs (mockable as constants until F04 lands).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Self-consumption ratio not credible → number doubted | Load-aware autarky formalised (§5.1); band shown (F11); §8.1 transparent derivation cited (§15). |
| Battery number looks implausible (the old −€20) | `V_BATTERY_8KWH` pins +€529/yr=+€44/mo gross, NET ≈€0 by design with the full sub-derivation (§8.1, §15). |
| Cloover APR/term unknown (D9) | 5 %/180 mo is a **labelled assumption** in §4 + every financing vector; one-line swap when Cloover confirms (Backlog §2 D9, §6). |
| **PV self-consumption double-counted (DD-1)** | First-class OPEN decision §0: credit PV self-consumption of HP/EV load in **exactly one place**; §8 per-bucket figures held **illustrative (±15 %)** until resolved; recommended model = credit in L1/L2, L3/L4 price grid/off-peak with no separate PV credit; headline `monthly_saving` unaffected. |
| Marginals don't sum to the headline | §6.1 exact-sum invariant is AC3 (exact equality, DD-1-independent); canonical-order, running-state computation enforced in the spec. |
| A price gets hard-coded in a vector | All prices are `PricingContext` inputs (R10); §10 note — only physics/policy constants are literal. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (the named vectors are committed fixtures).
- [ ] Lint + type-check clean for any fixture/helper code shipped with the spec (`ruff`+`mypy`).
- [ ] Contract honored — `contract_impact: none`; vector shapes map onto F02's `ScenarioResult` without drift.
- [ ] No secret added; **no hard-coded price** — every price enters via `PricingContext` (§12); only §10 physics/policy constants are literal.
- [ ] Every figure traces to a source or a labelled assumption — §8 numbers cite §8/§8.1; APR/term is the labelled D9 assumption; no invented precision.
- [ ] Reviewed by **Zhou** (per frontmatter) and signed off by Lukas as domain owner; merged to `main`; main is green.
- [ ] The demo happy-path holds after merge: baseline €435/mo exact; the ladder reproduces the §8 *structure* (Solar −, Battery ≈0, HP +, EV largest +, cumulative ≈ +€120/mo → after-payoff ≈ €364/mo) within ±15 % (illustrative pending DD-1, §0); and `Σ Δ_net == monthly_saving` exactly.

## 11. References

- `docs/design_plan/system_workflow.md` §5.1–§5.4 (four layers), §6.1 (marginals), §6.5 (financing), §7/§7.1 (confidence/dynamic tariff), §8/§8.1 (worked example + battery derivation), §10 (constants), §12 (price injection).
- `specs/domain/savings-engine.spec.md` — the artifact authored by this feature.
- `specs/api/openapi.yaml` (F02) — the `ScenarioResult` these vectors populate.
- Backlog `FEATURE_BACKLOG.md` §2 D4/D5/D6/D9, §5 (§8 traceability), §3 E0 row F03.
