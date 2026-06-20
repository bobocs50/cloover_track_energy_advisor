---
id: F11
title: Financing overlay + confidence band
epic: E1 Domain Core
owner: Lukas
reviewers: [Zhou]
priority: P3
mvp: true
status: Ready
branch: feat/F11-financing-confidence
depends_on: [F10]
contract_impact: reads
estimate_h: 2
---

# F11 — Financing overlay + confidence band

> **North-Star link:** turns gross savings into the honest North Star `monthly_saving = gross_saving −
> installment`, computes `saving_after_payoff` and `break_even_month`, and wraps the number in a ±band
> with the biggest driver named — defending and explaining the headline (§6.5, §7).

## 1. Intent (what & why)

F11 is the financing overlay (the anchor) and the confidence layer. It applies subsidies (KfW 458,
0 % VAT, EV grant €0), computes the annuity installment on `capex_after_subsidy − downpayment`, and
derives `monthly_saving`, `saving_after_payoff` and `break_even_month` (§6.5). It then attaches the §7
confidence treatment: the four certainty drivers, a ±band, the biggest-driver line, and a sensitivity
on the three riskiest inputs. **The financing APR/term (5 % / 180 mo) is a TBC labelled assumption
(decision D9) — the one genuine unknown — and must be surfaced as such.**

## 2. Scope

**In scope**
- `annuity(capex_after_subsidy − downpayment, apr, term_months)` as the installment primitive (used by F10's `Δ_installment` too).
- Subsidies: KfW 458 (**50 %** fossil→HP per D4, **30 %** HP→HP, capped **70 % / €21,000**); **0 % VAT** on PV/battery (§12(3) UStG); **EV grant €0** (Umweltbonus ended, BAFA).
- `monthly_saving = gross_saving − installment`; `saving_after_payoff = gross_saving`; `break_even_month = first month cumulative_net ≥ 0`.
- §7 confidence: the four drivers (irradiance, dynamic tariff, subsidies, self-consumption ratio), a ±band, and the **biggest-driver** line.
- Sensitivity analysis on the **3 riskiest inputs** (dynamic-tariff spread, self-consumption/autarky, KfW grant %).
- **Flagging APR/term 5 %/180 mo as a TBC labelled assumption (D9).**

**Out of scope** (explicitly, to prevent creep)
- The marginal ladder / optimiser / up-sell → **F10** (§6.1–§6.4); F11 overlays financing onto the chosen rung.
- The 8760-h self-consumption simulation → 🔶 stretch (D5); MVP uses the heuristic band on the load-aware autarky model.
- Live SMARD/PVGIS pulls → adapters F13/F14; F11 consumes the (possibly seeded) spread/yield, it does not fetch.
- Prices and capex values themselves — injected via `PricingContext` from `price_catalog` (§12); KfW %/VAT %/grant are §10 policy constants.

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | `capex_after_subsidy = capex − subsidies`, applied per component. | §6.5 |
| R2 | PV + battery: **0 % VAT** already (§12(3) UStG); no further federal grant assumed. | §6.5, §10 |
| R3 | Heat pump **Case A** (fossil→HP): KfW 458 **30 % base + Klima-Geschwindigkeitsbonus 20 % = 50 %** default, capped **70 % of eligible cost (cap €30,000 → max €21,000)**. | §6.5, §10, D4 |
| R4 | Heat pump **Case B** (old HP→new HP): **no Klima-bonus** → default modelled **30 %** (+ income/efficiency bonuses if applicable); same 70 %/€21k cap. | §6.5, §5.3, D4 |
| R5 | EV charger: **€0** subsidy (Umweltbonus ended 17 Dec 2023, BAFA) — wallbox capex only. | §6.5, §10 |
| R6 | `installment = annuity(capex_after_subsidy − downpayment, annual_rate, term_months)`. | §6.5 |
| R7 | `monthly_saving = gross_saving − installment` (honest: may be ≈0/neg early); `saving_after_payoff = gross_saving`; `break_even_month = first month cumulative_net ≥ 0`. | §6.5 |
| R8 | Attach the §7 four certainty drivers each with its confidence treatment, populate `ScenarioResult.confidence{band_eur, low_eur, high_eur, biggest_driver}` (the ±band) and name the **biggest driver** (self-consumption ratio) in `biggest_driver`. | §7 |
| R9 | Run sensitivity on the **3 riskiest inputs**: dynamic-tariff spread (widest band), self-consumption/autarky factor, KfW grant % (range 30–70 %). | §7 |
| R10 | **APR/term default 5 % / 180 mo is a TBC labelled assumption (D9)** — emit it flagged so the UI shows it as editable/uncertain. | §6.5, §10, D9 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> Every number cites an official/primary source and a fallback. No hard-coded prices — capex via
> `PricingContext` from `price_catalog` (§12); KfW %/VAT %/grant/spread are §10 policy/physics constants.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| KfW 458 grant | 30 % base → A 50 % (base+Klima) · B 30 %; cap **70 % / €21,000** | KfW (official §6.5) | as stated (D4) | §6.5 · L3 capex |
| PV/battery VAT | **0 %** (§12(3) UStG) | UStG (official §10) | 0 % | §6.5 · L1/L2 capex |
| EV purchase grant | **€0** (Umweltbonus ended 2023) | BAFA (official §10) | €0 | §6.5 · L4 |
| Financing APR · term | **5 % · 180 mo — Cloover real TBC (D9)** | Cloover product (§10) | 5 % / 180 mo seeded | §6.5 · annuity |
| Local irradiance | PVGIS per lat/lon | EU JRC (§7) | const 980 kWh/kWp | §7 · band (driver 1) |
| Dynamic-tariff spread | SMARD/EPEX day-ahead; seeded **€0.12/kWh** | SMARD (§7, §10) | seeded €0.12 | §7 · band (driver 2, widest) |
| Self-consumption autarky | 0.30 PV-only · ~0.60 +batt (load-aware) | BSW/HTW Berlin (§7, §10) | as stated | §7 · band (driver 4, biggest) |

Key formula(s), copied verbatim from §6.5 so the implementer codes against one definition:
```
capex_after_subsidy = capex − subsidies
   PV + battery:  0 % VAT already (§12(3) UStG, since 2023) → no further federal grant assumed
   heat pump A:   fossil → HP — KfW 458 — 30 % base + bonuses, capped 70 % of eligible cost
                  (cap €30,000 → max €21,000; a 2026 efficiency bonus may lift toward €23,500).
                  Default modelled 50 % (base 30 % + Klima-Geschwindigkeitsbonus 20 %).
   heat pump B:   old HP → new HP — **no Klima-bonus** (needs a fossil/non-renewable removal),
                  so default modelled **30 %** (base; + income/efficiency bonuses if applicable).
   EV charger:    €0 (Umweltbonus ended 17 Dec 2023, BAFA) — wallbox capex only (no vehicle financed)
installment = annuity(capex_after_subsidy − downpayment, annual_rate, term_months)
              # contract defaults: term 180 mo, APR 5 % — REPLACE with Cloover's real product (confirm)
monthly_saving      = gross_saving − installment        # North Star (honest: may be ≈0/neg early)
saving_after_payoff = gross_saving
break_even_month    = first month cumulative_net ≥ 0
```
§7 confidence drivers (verbatim mapping): **Local irradiance** (L1, ±8 % band) · **Dynamic tariff**
(L2/L4, widest band, own line) · **Applicable subsidies** (L3, modelled 50 %, range 30–70 % shown) ·
**Self-consumption ratio** (L1/L2, the single biggest driver → named in the UI band).
**APR/term 5 %/180 mo = TBC labelled assumption (decision D9 — the one genuine unknown; ask a Cloover mentor early).**

## 5. Contract surface  *(if contract_impact ≠ none)*

- **Reads only** — `contract_impact: reads`. Populates the frozen `ScenarioResult` fields: `installment_eur_month`, `monthly_saving_eur` (North Star), the discrete `saving_after_payoff_eur` and `break_even_month`, and `payback_note`, per §14.1. The ±band and biggest-driver land in the typed `ScenarioResult.confidence{band_eur, low_eur, high_eur, biggest_driver}`; the sensitivity rides along as `assumptions[]` (`Assumption{field,value,source,editable}`) metadata — all already present in the frozen F02 contract.
- New/changed schema objects: none — F02 is frozen and carries `confidence{band_eur,low_eur,high_eur,biggest_driver}`, `saving_after_payoff_eur`, `break_even_month` and `assumptions[]`.
- Backwards-compatible? Yes — overlays financing/confidence onto frozen fields; reads only.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (annuity + KfW Case A, §8)** — Given HP capex €22,000 at **50 % KfW** ⇒ `capex_after_subsidy = €11,000`, when `annuity(11000, 5 %, 180)` is computed, then `installment ≈ €87/mo` (§8 table), within ±€1.
- [ ] **AC2 (0 % VAT + battery installment, §8)** — Given PV €13,050 (0 % VAT) and battery €5,600, when annuities are computed at 5 %/180 mo, then `installment ≈ €103/mo` (PV) and `≈ €44/mo` (battery) per §8.
- [ ] **AC3 (North Star + after-payoff, §8 — ILLUSTRATIVE pending DD-1)** — Given the full §8 bundle, when financing is overlaid, then `monthly_saving` is **positive** (illustrative **≈ +€100–120/mo** now, ±15 %, DD-1-dependent — not a hard +€120) and `saving_after_payoff` is **≫ now** (illustrative **≈ €364/mo** gross). `monthly_saving = gross_saving − installment` and `= Σ Δ_net` (F10) is the euro-exact identity; the magnitude is illustrative pending DD-1 (F03 §0).
- [ ] **AC4 (break-even, §8 — structure exact, magnitude illustrative)** — Given the §8 cumulative-net path (illustrative ≈ −€24 → −€24 → −€4 → +€120 at the full rung; per-rung euros ±15 % pending DD-1), when `break_even_month` is computed, then it is the first month `cumulative_net ≥ 0` (this **definition/logic is exact**) and the `payback_note` reflects "≈ cost-neutral early → ≈ €364/mo after payoff". Note the after-payoff running sum is **€231 (±€1 rounding)**, not exactly €230.
- [ ] **AC5 (KfW Case B nuance)** — Given a heat-pump **Case B** (old HP→new HP) with capex €22,000, when the grant is applied, then it is **30 %** (not 50 %) ⇒ `capex_after_subsidy = €15,400`, and the installment is correspondingly higher (no Klima-Geschwindigkeitsbonus) — §5.3/§6.5.
- [ ] **AC6 (KfW cap)** — Given an eligible cost above the cap, when KfW 458 is applied, then the grant is capped at **70 % of eligible cost, max €21,000** (cap €30,000 eligible).
- [ ] **AC7 (confidence band + biggest driver, §7)** — Given the §8 result, when the band is produced, then `ScenarioResult.confidence.band_eur` is ≈ **±€35** (per §9 dashboard) with `confidence.low_eur`/`high_eur` bracketing it and `confidence.biggest_driver` set to the **self-consumption ratio**, and the dynamic-tariff/arbitrage uncertainty shown on its own (widest) line.
- [ ] **AC8 (sensitivity, §7)** — Given the 3 riskiest inputs, when each is swept (dynamic spread, autarky factor, KfW % over 30–70 %), then `monthly_saving` moves monotonically and the reported band brackets the sweep.
- [ ] **AC9 (D9 assumption flag)** — Given the default financing, when the result is emitted, then **APR 5 % / term 180 mo is flagged as a TBC labelled assumption (D9)**, editable, and overriding it tightens/shifts the band live.
- [ ] **AC10 (honesty/edge — early ≈0/negative)** — Given solar-only on the §8 small base load, when financing is overlaid, then `monthly_saving` is reported **honestly as mildly negative** (not floored at 0; illustrative ≈ −€24/mo, ±15 %), with `saving_after_payoff` positive (illustrative ≈ €80/mo). The **sign and the not-floored honesty are the assertion**; the exact euro is illustrative pending DD-1.

## 7. Test plan

- **Unit** (pure domain only, zero I/O): **exact** fixtures `annuity(11000, 5 %, 180) ≈ €87`, `annuity(5600,…) ≈ €44`, `annuity(13050,…) ≈ €103`, `annuity(1200,…) ≈ €10` (DD-1-independent reproducible intermediates); KfW 50 % (A) vs 30 % (B) vs 70 %/€21k cap (exact); 0 % VAT PV/battery; EV grant €0; break-even **logic** on the §8 cumulative path (per-rung euros illustrative ±15 % pending DD-1, after-payoff sum €231 ±€1); ±€35 band with self-consumption as biggest driver; sensitivity sweep on the 3 riskiest inputs; D9 APR/term flagged.
- **Integration / contract**: assert `installment_eur_month`, `monthly_saving_eur`, `saving_after_payoff_eur`, `break_even_month`, `payback_note`, the `confidence{band_eur,low_eur,high_eur,biggest_driver}` block and the `assumptions[]` metadata serialise correctly on the chosen rung from F10 (against the frozen F02 contract).
- **Demo-safety**: deterministic with seeded spread (€0.12) and the D9 default APR/term; `?fixture` golden payload reproduces §8 — **€87 installment exact**; the headline (≈ +€120/mo now → ≈ €364/mo after, ±€35) is **captured from the engine fixture (F24), not hand-pinned** (illustrative pending DD-1); no live KfW/SMARD/PVGIS call in the engine.

## 8. Dependencies & interfaces

- **Upstream (needs):** F10 (the chosen rung + per-layer `Δ_capex`/`Δ_gross` and `cumulative_net` path); the `kfw_case` flag from F08 (A vs B grant rate); a `PricingContext` (F12, §12) for capex; the (seeded or live) dynamic-tariff spread and irradiance band inputs. F03 §8 vectors.
- **Downstream (feeds):** F17 (`/recommend` serialises `installment_eur_month`/`monthly_saving_eur`/`payback_note` + confidence), F21/F23 (UI hero curve, break-even, confidence chip + assumptions drawer), F16 (LLM prose asserts against these numbers).
- **Mock until ready:** the `annuity()` primitive is provided here for F10 to call; blocked consumers mock F11 with the §8 financing fixture (**€87 installment exact**; headline ≈ +€120/mo now → ≈ €364/mo after, ±€35 — illustrative pending DD-1) from the frozen contract.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| **Cloover APR/term unknown (D9)** | Default 5 %/180 mo as a **labelled assumption** in the UI + this spec (AC9); ask a mentor in P0; one-line swap if confirmed — §16/D9. |
| Over-claiming subsidies (esp. EV) | EV grant **€0**; KfW capped **70 %/€21k**; Case B HP→HP modelled at **30 %** (no Klima-bonus); official sources cited — §6.5, §15. |
| Battery/headline number doubted | Honest ≈0/negative early values surfaced (AC10); transparent break-even + after-payoff; biggest driver named — §8.1, §15. |
| **Headline magnitude over-pinned (DD-1)** | The §8 headline (+€120/mo now, €364 after) is **illustrative ±15 %** until DD-1 (F03 §0) resolves PV self-consumption attribution; the euro-exact assertions are the **annuities** and the `monthly_saving = gross − installment = Σ Δ_net` identity, not a pinned headline magnitude. |
| Confidence band understated | Dynamic-tariff/arbitrage on its own widest line; sensitivity on the 3 riskiest inputs brackets the band — §7. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 financing/band vectors and the D9 flag).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored (reads only; financing + confidence written to the frozen `ScenarioResult.confidence{band_eur,low_eur,high_eur,biggest_driver}`, `saving_after_payoff_eur`, `break_even_month` and `assumptions[]` fields — no contract change needed, F02 is frozen).
- [ ] No secret added to the frontend bundle; no hard-coded price (capex via `PricingContext`); KfW/VAT/grant cited to §10.
- [ ] Every figure traces to a source or a labelled assumption — **APR/term explicitly flagged TBC (D9)**, no invented precision.
- [ ] Reviewed by **Zhou** (independent, per frontmatter — domain feature owned by Lukas, reads the frozen F02 contract); merged to `main`; main is green.
- [ ] The demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §6.5, §7, §7.1, §8, §8.1, §10, §16 (D9)
- `specs/api/openapi.yaml` (`ScenarioResult.installment_eur_month`, `monthly_saving_eur`, `payback_note`) · `specs/domain/savings-engine.spec.md` (§8 vectors via F03)
