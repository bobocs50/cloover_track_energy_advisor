---
id: F09
title: Layer 4 — EV charger (mobility bucket)
epic: E1 Domain Core
owner: Lukas
reviewers: [Lukas]
priority: P2
mvp: true
status: Ready
branch: feat/F09-layer4-ev-charger
depends_on: [F05]
contract_impact: reads
estimate_h: 1.5
---

# F09 — Layer 4 — EV charger (mobility bucket)

> **North-Star link:** computes the **mobility bucket €/month** the wallbox adds —
> `baseline_mobility_cost/12 − home_charge_cost/12` — and raises `annual_consumption_kwh` (big flexible
> load), lifting L1/L2 self-consumption, directly moving the headline `monthly_saving` (§5.4, §6.2).

## 1. Intent (what & why)

Layer 4 is a pure module that prices home EV charging against the cost it displaces and reports the
monthly mobility-cost reduction on the running state (§5.4). It must serve **both** offer cases from the
§3.2 matrix: **Case A** petrol/diesel car → EV (saving = expensive fuel → cheap home charging), and
**Case B** household **already drives an EV but has no home charger** (`existing_ev ∧ ¬existing_ev_charger`)
→ adding a wallbox swaps expensive public charging for cheap home charging. Both compute the same
`ev_kwh_year`; they differ only in the baseline displaced and the capex (Case B = wallbox alone). EV is
typically the single biggest saver in the bundle (§8).

## 2. Scope

**In scope**
- `ev_kwh_year = km_year × 18/100` (km is canonical from intake §3.3; F05 has already done €→km).
- `home_charge_cost` at `home_blended_price ≈ €0.20/kWh` (PV surplus + off-peak dynamic + occasional public).
- Baseline per case: Case A petrol/diesel fuel cost; Case B public charging at `≈ €0.45/kWh`.
- Accumulating `ev_kwh_year` into `annual_consumption_kwh` so L1/L2 are re-evaluated higher (§6.2).
- Street-only-parking fallback: Case B → not offered; Case A → blend rises (~€0.30) and saving shrinks honestly.

**Out of scope** (explicitly, to prevent creep)
- The vehicle purchase/financing — capex here is the **wallbox only** (no vehicle financed); EV grant €0 (§6.5, F11).
- Hourly EV-charging scheduling simulation against live SMARD prices → 🔶 stretch (§7.1); MVP uses the seeded blend.
- €→km conversion itself → **F05** (§3.3); Layer 4 consumes `km_year` directly.
- Annuity/subsidy math → **F11** (§6.5). Live fuel/public-charge prices — injected via `PricingContext` (§12).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | `ev_kwh_year = km_year × ev_consumption_kwh_per_100km / 100` with EV consumption = 18 kWh/100 km. | §5.4, §3.3, §10 |
| R2 | `home_charge_cost = ev_kwh_year × home_blended_price` with `home_blended_price ≈ €0.20/kWh` (PV ≈40 % + off-peak ≈50 % + public ≈10 %). | §5.4, §10 |
| R3 | Case A baseline: `current_fuel_cost = km_year/100 × consumption_l_per_100km × fuel_price` (petrol 7.0 L/100 km, diesel 6.0 L/100 km). | §5.4, §3.3, §10 |
| R4 | Case B baseline: `current_charge_cost = ev_kwh_year × public_charge_price` at `≈ €0.45/kWh`. | §5.4, §3.2, §10 |
| R5 | `annual_consumption_kwh += ev_kwh_year` so L1/L2 self-consumption is re-evaluated on the running state. | §5.4, §6.2 |
| R6 | Bucket €/mo = `baseline_mobility_cost / 12 − home_charge_cost / 12`. | §5.4 |
| R7 | Street-only parking (Site-Check `🟡`): **Case B → Layer 4 not offered** (Δ = 0); **Case A → drop PV share**, blend rises to ~€0.30/kWh, saving shrinks. | §5.4, §3.2, §4 |
| R8 | Offer gating: EV + existing charger ⇒ Δ = 0; `NONE` (no car) ⇒ Δ = 0 (consistent with the offer matrix). | §3.2, §6.3 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> Every number cites an official/primary source and a fallback. No hard-coded prices — fuel/public/retail
> prices come from `price_catalog` (§12) via `PricingContext`; this table holds physics/policy constants.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| EV consumption | 18 kWh/100 km | class default (§10) | 18 const | L4 · ev_kwh_year |
| Petrol / diesel consumption | 7.0 / 6.0 L/100 km | class default / ADAC (§10) | as stated | L4 · Case A baseline |
| EV home blended charge | €0.20/kWh | derived (PV+off-peak+public) (§10) | €0.20 const | L4 · home_charge_cost (both cases) |
| EV public charge price | €0.45/kWh | CPO public AC/DC avg (Destatis/Ladesäulenregister) (§10) | €0.45 const | L4 Case B · public baseline |
| `petrol_per_litre` / `diesel_per_litre` / `public_charge_per_kwh` | €1.85 / €1.75 / €0.45 | `price_catalog` §12 (Destatis/ADAC) | seeded §12 values | L4 · prices (injected) |
| Dynamic-tariff spread (net) | €0.12/kWh (seeded; live toggle) | SMARD / EPEX (§7, §10) | seeded €0.12 | L4 · off-peak share of blend |
| EV purchase grant | €0 (Umweltbonus ended 2023) | BAFA (official §6.5) | €0 | §6.5 (F11) · L4 |

Key formula(s), copied verbatim from §5.4 so the implementer codes against one definition:
```
# Energy need — km is canonical (intake §3.3). For an existing EV, km may be given directly,
# or backed out of the current charging spend at the public price.
ev_kwh_year = km_year × ev_consumption_kwh_per_100km / 100          # EV ≈ 18 kWh/100 km
annual_consumption_kwh += ev_kwh_year                              # ← flexible load, big self-cons. uplift
home_charge_cost = ev_kwh_year × home_blended_price                 # ≈ €0.20/kWh (blend below)

# Baseline being displaced:
#   Case A (petrol/diesel): current_fuel_cost = km_year/100 × consumption_l_per_100km × fuel_price
#   Case B (EV, no charger): current_charge_cost = ev_kwh_year × public_charge_price   # ≈ €0.45/kWh public avg
LAYER-4 mobility bucket €/mo = baseline_mobility_cost / 12 − home_charge_cost / 12
```
`home_blended_price ≈ €0.20/kWh` = PV surplus (≈ free, ~40 %) + off-peak dynamic tariff (~50 %) + occasional public DC (~10 %); charging scheduled into the cheapest dynamic-tariff hours (§7).
Case B economics: the saving is purely the price gap `public_charge_price − home_blended_price` (≈ €0.45 → €0.20) over `ev_kwh_year`, against a small wallbox capex — usually strongly net-positive.
Street-only: Layer 4 not offered (Case B) or PV share dropped so the blend rises (~€0.30) and the saving shrinks honestly (Case A).

## 5. Contract surface  *(if contract_impact ≠ none)*

- **Reads only** — `contract_impact: reads`. Consumes `Household` fields frozen in F02: `mobility {kind, km_month | eur_month}` (km canonical via F05), `existing_ev: bool`, `existing_ev_charger: bool`, and the Site-Check `parking` / street-only feasibility flag.
- New/changed schema objects: none. Output flows through `ScenarioResult.breakdown.mobility_eur_month` (existing field, §14.1).
- Backwards-compatible? Yes — no schema change; this feature only reads the F02 contract.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (Case A worked example, §8 — exact intermediate + honest gross; see DD-1)** — Given the §8 home (€160/mo petrol, 14,800 km/yr, on the running state with PV+battery+HP already ticked), when Layer 4 is added, then:
  - **(exact, DD-1-independent)** `ev_kwh_year = 2,664 kWh` (= 14,800 × 18/100);
  - **(honest gross, recommended DD-1 model)** mobility bucket Δ gross ≈ **+€115/mo** = fuel **€159.7/mo** (14,800/100 × 7.0 L × €1.85 / 12) − home charge **€44.4/mo** (2,664 × €0.20 / 12), where the €0.20 home blend is the **off-peak/grid** price **without a separate free-PV credit** (the PV→EV self-consumption is credited in L1/L2 on the running state, §6.2, not a second time here);
  - the higher **≈ +€133/mo** figure in the §8 table is **illustrative** and only holds if the EV's PV self-consumption is credited in this bucket instead of L1/L2 — **per DD-1 (F03 §0) it must be credited in exactly one place**. Assert ±15 %, illustrative pending DD-1.
- [ ] **AC2 (Case A net, §8 — ILLUSTRATIVE pending DD-1)** — Given AC1 plus the F11 installment €10/mo (wallbox capex €1,200, annuity(1200,5 %,180) ≈ €10), when net is formed, then EV is the **largest positive** rung and the cumulative net becomes **positive** (illustrative **Δ net ≈ +€115–124/mo**, headline cumulative **≈ +€100–120/mo** depending on the DD-1 accounting; not a hard +€120). The AC3 exact-sum invariant (F03) and the sign remain euro-exact.
- [ ] **AC3 (`annual_consumption_kwh` lift, §6.2)** — Given Layer 4 added on the running state, when L1/L2 are re-evaluated, then `annual_consumption_kwh` increases by exactly `ev_kwh_year (= 2,664)` and PV/battery self-consumption value rises (the cumulative-interaction proof). **This L1/L2 uplift is where the EV's PV self-consumption is credited under the recommended DD-1 model — so it is not also credited in the L4 home-charge blend (no double-count).**
- [ ] **AC4 (Case B charging swap)** — Given `existing_ev ∧ ¬existing_ev_charger` with the same `km_year`, when Layer 4 is added, then capex is the **wallbox only** and the saving = `ev_kwh_year × (0.45 − 0.20)` (public → home blend), with no vehicle assumed.
- [ ] **AC5 (street-only fallback)** — Given Site-Check returns street-only parking: in **Case B** Layer 4 is **not offered** (Δ = 0); in **Case A** `home_blended_price` rises to ~€0.30/kWh and the saving shrinks accordingly.
- [ ] **AC6 (honesty/edge — already served / no car)** — Given `existing_ev ∧ existing_ev_charger`, then Layer 4 Δ = 0 ("already installed ✓ — no capex"); given mobility kind `NONE`, then Δ = 0.

## 7. Test plan

- **Unit** (pure domain only, zero I/O): the §8 Case A vector (14,800 km → **2,664 kWh** exact; Δ gross **≈ +€115/mo** under the recommended DD-1 model = fuel €159.7 − home €44.4; the +€133 variant is illustrative and depends on where PV self-consumption is credited, F03 §0) as a fixture; Case B price-gap vector (public €0.45 → home €0.20); street-only blend ~€0.30 (Case A) and not-offered (Case B); `NONE` and EV+charger ⇒ Δ 0; petrol vs diesel L/100 km.
- **Integration / contract**: assert the value lands in `breakdown.mobility_eur_month` and that `annual_consumption_kwh` passed to L1/L2 reflects the EV lift (engine-level, against the frozen F02 contract shapes).
- **Demo-safety**: prices injected from a seeded `PricingContext` (offline); `?fixture` golden payload reproduces the §8 numbers; no live fuel/public-charge call in the engine.

## 8. Dependencies & interfaces

- **Upstream (needs):** F05 (km-canonical mobility + existing-equipment folding + baseline), a `PricingContext` (F12 from `price_catalog`, §12) for petrol/diesel/public-charge prices, and the Site-Check street-only flag (F15) for the parking fallback. F03 supplies the §5–§8 test vectors.
- **Downstream (feeds):** F10 (marginal/optimiser — Layer 4 Δ on the running state) and F11 (financing — wallbox capex + EV grant €0).
- **Mock until ready:** consumers mock Layer 4 with a fixture pair (Case A: ev_kwh **2,664** exact, Δ gross **≈ +€115/mo** recommended-model — +€133 only if PV credited here per DD-1; Case B: price-gap example) from the frozen contract; the street-only flag can be mocked as a boolean.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| EV-charger offer (Case B) over-sold | Saving = price-gap only (`public − home blend`); optimiser (F10) drops it if net-negative — §15. |
| Blended price too optimistic | `home_blended_price` documented as PV/off-peak/public mix; street-only path raises it to ~€0.30 honestly; band widened by the dynamic spread (§7). |
| **PV→EV self-consumption double-counted (DD-1)** | The EV load's PV self-consumption is credited in **one** place only (F03 §0). Recommended model: price L4 home charging at the **off-peak/grid blend (no free-PV share)** and let the PV→EV self-consumption surface in the re-evaluated L1/L2 bucket (§6.2). Honest gross ≈ **+€115/mo** (fuel €159.7 − home €44.4); the €0.20-blend-with-PV variant (≈ +€133) is illustrative and must not also be credited in L1/L2. |
| Over-claiming EV subsidy | EV purchase grant **€0** (Umweltbonus ended 2023, BAFA); wallbox capex only — §6.5, §15. |
| Hard-coded fuel prices drift | All prices injected via `PricingContext` from `price_catalog` (§12); none imported in the engine — §15. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 worked-example vector: `ev_kwh_year = 2,664` exact; Δ gross ≈ +€115/mo honest, illustrative pending DD-1).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored (reads only; value flows via `breakdown.mobility_eur_month`); no payload drift.
- [ ] No secret added to the frontend bundle; no hard-coded price (reads `price_catalog` via `PricingContext`).
- [ ] Every figure traces to a §10/§12 source or a labelled assumption (no invented precision).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §5.4, §3.2, §3.3, §6.3, §7, §10, §12
- `specs/api/openapi.yaml` · `specs/domain/savings-engine.spec.md` (§8 vectors via F03)
