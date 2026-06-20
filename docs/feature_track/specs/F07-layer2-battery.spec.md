---
id: F07
title: Layer 2 — Battery (electricity, 2nd value stream)
epic: E1 Domain Core
owner: Lukas
reviewers: [Lukas]
priority: P2
mvp: true
status: Ready
branch: feat/F07-layer2-battery
depends_on: [F06]
contract_impact: reads
estimate_h: 2
---

# F07 — Layer 2 — Battery (electricity, 2nd value stream)

> **North-Star link:** Layer 2 adds the **second electricity value stream** (extra self-consumption +
> dynamic-tariff arbitrage). At this rung it nets ≈€0/mo by design — and the spec must *prove* why
> it climbs once L3/L4 load is added (§6.2), which is the literal challenge answer.

## 1. Intent (what & why)

Implement the §5.2 pure module on top of Layer 1: (a) battery lifts autarky 0.30→~0.60 → extra
self-consumption, **net of lost feed-in**; (b) dynamic-tariff arbitrage on the remaining cycles. No
double-counting: PV charges the battery first (that energy is already self-consumption), only the
*remaining* cycles are pure arbitrage on their own line. Existing-battery delta only; deterministic,
zero I/O; spread and prices injected (§7.1, §12). Encodes the **§8.1 honest derivation** (≈€0/mo net)
as a test vector.

## 2. Scope

**In scope**
- `added_kwh = max(0, recommended_batt_kwh − existing_battery_kwh)`,
  `total_kwh = existing_battery_kwh + added_kwh` (existing battery → delta only, §3.2).
- (a) Extra self-consumption: `extra_self_kwh = (autarky_with_batt − autarky_pv_only) ×
  annual_consumption_kwh` (capped ≤ unused yield); valued at retail **minus** lost feed-in.
- (b) Arbitrage: `total_kwh × cycles_per_year × round_trip × dynamic_spread`
  (cycles **300**, round_trip **0.90**, seeded spread **€0.12/kWh** net).
- Bucket €/mo `+=` `(extra_self_value + arbitrage_value)/12`.
- Encode the §8.1 sub-derivation as the canonical battery test vector; document the §6.2 climb.

**Out of scope** (explicitly, to prevent creep)
- Layer-1 sizing/yield/self-consumption baseline → F06 (consumed here as running state).
- HP/EV load that *raises* `annual_consumption_kwh` (and thus battery value) → F08/F09 add the load;
  F07 just re-evaluates on whatever running-state `annual_consumption_kwh` it receives (§6.2).
- Live SMARD/aWATTar spread pull + cache → dynamic-tariff adapter F14; F07 takes the seeded €0.12.
- Battery capex / annuity → financing overlay F11.

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | `added_kwh = max(0, recommended_batt_kwh − existing_battery_kwh)`; `total_kwh = existing + added`. | §5.2, §3.2 |
| R2 | `extra_self_kwh = (autarky_with_batt − autarky_pv_only) × annual_consumption_kwh`, capped ≤ unused yield. | §5.2 |
| R3 | `extra_self_value = extra_self_kwh × retail_price − extra_self_kwh × 0.0778` (net of lost feed-in). | §5.2 |
| R4 | `arbitrage_value = total_kwh × cycles_per_year × round_trip × dynamic_spread` (300 · 0.90 · €0.12). | §5.2, §7.1 |
| R5 | Bucket €/mo `+=` `(extra_self_value + arbitrage_value)/12`. | §5.2 |
| R6 | No double-count: PV→battery energy counts as self-consumption; only remaining cycles are pure arbitrage (own line, wider band). | §5.2, §7.1 |
| R7 | Arbitrage credited **only** on the dynamic tariff (part of the Cloover bundle). | §5.2 |
| R8 | Re-evaluating with a larger running-state `annual_consumption_kwh` (after L3/L4) yields a **larger** battery value. | §6.2 |
| R9 | Pure & deterministic; zero I/O; spread and prices injected. | §2, §1, §12 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> No hard-coded prices. `retail_price`, `feedin_per_kwh` (€0.0778) and the battery €/kWh come from
> `PricingContext` (`price_catalog`, §12). The dynamic spread is a seeded MVP constant (§7.1). This
> table pins the physics/policy constants and the formula.

| Quantity / call | Value | Official source | Fallback | Used in |
|---|---|---|---|---|
| Autarky PV-only → +battery | 0.30 → ~0.60 | BSW/HTW Berlin (§10) | const 0.30/0.60 | L2 · extra_self_kwh |
| Battery cycles/yr | **300** | engineering/datasheets (§10) | const 300 | L2 · arbitrage_value |
| Round-trip efficiency | **0.90** | datasheets (§10) | const 0.90 | L2 · arbitrage_value |
| Dynamic-tariff spread (net) | **€0.12/kWh** (seeded; live toggle) | **SMARD/EPEX** day-ahead (§7.1, §10) | seed €0.12 | L2 · arbitrage_value |
| `retail_per_kwh` | €0.37/kWh | Destatis/BNetzA → `price_catalog` (§12) | seed €0.37 | L2 · extra_self_value |
| `feedin_per_kwh` | **€0.0778/kWh** | Bundesnetzagentur EEG (§10) | seed €0.0778 | L2 · lost feed-in |

§5.2 Layer-2 pseudocode, copied **verbatim** so the implementer codes against one definition:
```
added_kwh   = max(0, recommended_batt_kwh − existing_battery_kwh)   # existing battery handled here
total_kwh   = existing_battery_kwh + added_kwh

# (a) Extra self-consumption: battery lifts autarky 0.30 → ~0.60 (shift midday surplus to evening)
extra_self_kwh   = (autarky_with_batt − autarky_pv_only) × annual_consumption_kwh     # ≤ unused yield
extra_self_value = extra_self_kwh × retail_price − extra_self_kwh × 0.0778  # net of lost feed-in
# (b) Dynamic-tariff arbitrage: charge cheap hours, discharge expensive hours (see §7 dynamic tariff)
arbitrage_value  = total_kwh × cycles_per_year × round_trip × dynamic_spread
                   # cycles≈300, round_trip≈0.90, dynamic_spread from SMARD/EPEX day-ahead (§7)

LAYER-2 electricity bucket €/mo += (extra_self_value + arbitrage_value) / 12
```
No double-counting: PV charges the battery first (counts as self-consumption); only the *remaining*
cycles are pure arbitrage, on their own line with a wider confidence band. Arbitrage is credited
**only** on the dynamic tariff — which is part of the Cloover bundle.

**§8.1 honest derivation (THE canonical test vector — base load 3,081 kWh/yr, 8 kWh battery, before
HP/EV load):**
```
(a) Extra self-consumption: autarky 0.30 → 0.60 ⇒ +0.30 × 3,081 = +924 kWh × €0.37   = +€342/yr
(b) Less feed-in (stored, not exported):                      −924 kWh × €0.0778      =  −€72/yr
(c) Dynamic-tariff arbitrage: 8 kWh × 300 cycles × 0.90 × €0.12 spread                = +€259/yr
    ── battery gross  = 342 − 72 + 259                                                = +€529/yr  = +€44/mo
    ── installment (€5,600 @ 5 % / 180 mo)                                            = −€44/mo
    ── NET at this rung                                                               ≈  €0/mo
```
**Why it climbs (§6.2):** add Layers 3–4 (≈7,400 kWh of new annual load) → `annual_consumption_kwh`
rises → the same battery cycles displace far more expensive grid import → its value climbs well above
its €44/mo installment. The battery is the **enabler** that pays off once the loads are electrified.

## 5. Contract surface  *(contract_impact = reads)*

- Reads `existing_battery_kwh` and the running-state input (`annual_consumption_kwh`, `annual_yield_kwh`
  from F06, prices, seeded spread) per `openapi.yaml` (F02). Output increments
  `ScenarioResult.breakdown.electricity_eur_month`; arbitrage shown on its own line (§7.1, §9).
- New/changed schema objects: none (consumes the contract).
- Backwards-compatible? yes — read-only.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (§8.1(a) extra self-consumption gross)** — Given `annual_consumption_kwh=3081`,
  autarky 0.30→0.60, retail €0.37, then `extra_self_kwh ≈ 924.3` and gross self-consumption
  value ≈ **+€342/yr** (±€2).
- [ ] **AC2 (§8.1(b) lost feed-in)** — With AC1 and feed-in €0.0778, then lost feed-in ≈ **−€72/yr**,
  so `extra_self_value ≈ 342 − 72 ≈ +€270/yr` (±€2).
- [ ] **AC3 (§8.1(c) arbitrage)** — Given `total_kwh=8`, cycles 300, round_trip 0.90, spread €0.12,
  then `arbitrage_value ≈ 8×300×0.90×0.12 ≈ **+€259/yr**` (±€2).
- [ ] **AC4 (§8.1 battery gross & net — the headline honesty vector)** — Sum (a)+(b)+(c) ≈
  **+€529/yr ≈ +€44/mo gross**; against the €5,600 @ 5 %/180-mo installment (−€44/mo, from F11) the
  rung nets **≈ €0/mo** — exactly the §8 Battery row.
- [ ] **AC5 (no double-count)** — Energy PV puts into the battery is counted once (as
  self-consumption); arbitrage uses only the **remaining** cycles, returned on its own line — total
  battery value never exceeds extra-self + remaining-cycle arbitrage.
- [ ] **AC6 (existing-battery delta)** — Given `existing_battery_kwh=4`, `recommended_batt_kwh=8`,
  then `added_kwh==4`, `total_kwh==8`; self-consumption + arbitrage computed on **total** 8 kWh,
  capex (F11) on the added 4 kWh only.
- [ ] **AC7 (honesty/edge — §6.2 climb)** — Given the **same** 8 kWh battery but running-state
  `annual_consumption_kwh` raised by L3+L4 (~+7,400 kWh → ~10,500 kWh), then the recomputed battery
  value is **strictly greater** than the ≈€44/mo gross at the bare rung (AC4) — the documented reason
  a bigger bundle raises the saving (§6.2). Asserts the monotonic climb, not a fixed number.

## 7. Test plan

- **Unit** (pure, zero I/O): AC1–AC7 as vectors; the **§8.1 sub-derivation is the named golden
  fixture** (+€342 / −€72 / +€259 → +€529/yr → +€44/mo gross → ≈€0/mo net); a monotonicity property
  test: battery value is non-decreasing in `annual_consumption_kwh` (AC7); determinism +
  injected-spread/price test (no value imported); no-double-count invariant.
- **Integration / contract**: output increments `breakdown.electricity_eur_month`; arbitrage exposed
  on its own line per the frozen `openapi.yaml`/§9.
- **Demo-safety**: with seeded €0.12 spread and seeded `price_catalog`, the §8.1 fixture reproduces
  ≈€0/mo net offline — no SMARD call needed.

## 8. Dependencies & interfaces

- **Upstream (needs):** F06 (Layer-1 running state: `annual_consumption_kwh`, `annual_yield_kwh`,
  autarky baseline), injected `dynamic_spread` (F14 or seeded €0.12) and `PricingContext` (§12).
- **Downstream (feeds):** F10 (marginal ladder — battery rung Δ), F11 (financing nets the €44/mo
  installment), F22 (UI proof of the §6.2 climb).
- **Mock until ready:** consumers mock the §8.1 fixture (gross +€44/mo, net ≈€0/mo) until F07 merges;
  F14 mocked by injecting `dynamic_spread = 0.12`.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Battery number looks implausible (the old −€20 error) | encode the §8.1 transparent sub-derivation as the golden vector; it is ≈break-even by design (§8.1, §15). |
| Double-counting PV-charged energy as both self-consumption and arbitrage | PV charges first → self-consumption; only remaining cycles arbitrage, own line (R6, AC5, §5.2). |
| Arbitrage band too tight / over-claimed | seeded €0.12 net spread, widest band, on its own line, never blended into "certain" buckets (§7.1). |
| Reviewer doubts "bigger bundle = bigger saving" | AC7 monotonicity test proves the §6.2 climb mechanically. |
| Hidden price/spread import breaks purity | both injected; tests run with zero network and stubs (§12). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated unit tests (incl. the §8.1 +€529/yr → ≈€0/mo vector).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored: increments `breakdown.electricity_eur_month`; arbitrage on its own line; no drift.
- [ ] No secret in any bundle; no hard-coded price (retail/feed-in/battery € from `price_catalog`; spread seeded/injected).
- [ ] Every figure traces to a §10/§8.1 source or a labelled assumption (no invented precision).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §5.2, §8.1, §7.1, §6.2, §3.2, §10, §12
- `specs/api/openapi.yaml` · `specs/domain/savings-engine.spec.md` (F03)
