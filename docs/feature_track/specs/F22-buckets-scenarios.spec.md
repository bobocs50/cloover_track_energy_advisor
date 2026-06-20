---
id: F22
title: Bucket breakdown + scenario comparison + up-sell
epic: E3 Frontend
owner: Philips
reviewers: [Lukas]
priority: P3
mvp: true
status: Ready
branch: feat/F22-buckets-scenarios
depends_on: [F20, F21]
contract_impact: reads
estimate_h: 2
---

# F22 — Bucket breakdown + scenario comparison + up-sell

> **North-Star link:** explains *where* the `monthly_saving` comes from (electricity / heating / mobility),
> proves *why a bigger bundle saves more* by comparing the four ladder rungs, and converts with the inline
> up-sell line ("still on oil? the heat pump is €X/mo of your saving"). It decomposes and defends the headline.

## 1. Intent (what & why)

Render the three explanatory blocks below the hero (§9, §6.4): (1) **three bucket tiles** — Electricity /
Heating / Mobility €/mo — each **expandable to "why"** (self-consumption %, SCOP, off-peak charging);
(2) **scenario cards** for the four ladder rungs (☀️, ☀️+🔋, ☀️+🔋+♨️, full) with the **recommended one
highlighted**; (3) the **inline up-sell line** — the diff vs the next-smaller rung that names what the user
is still burning. All values are read from `Recommendation.alternatives[].breakdown` and `upsell` (engine
F10) — mock-first against the §8 golden payload. Refs §9, §6.4.

## 2. Scope

**In scope**
- **Three bucket tiles**: Electricity / Heating / Mobility €/mo, from
  `ScenarioResult.breakdown.{electricity,heating,mobility}_eur_month` of the selected rung (§9).
- **Expandable "why" per tile**: Electricity → self-consumption % (autarky); Heating → SCOP (and Case-B
  efficiency delta); Mobility → off-peak/home charging blend — the §7/§5 drivers in plain language (§9).
- **Scenario cards** for the **four ladder rungs** (the contract `alternatives[]`): each shows its
  `monthly_saving_eur` and a one-line summary; the **optimiser-recommended rung is highlighted** (`best`, §6.4).
- **Inline up-sell line**: the diff vs the next-smaller rung, surfaced as copy that names the still-burned
  fuel — e.g. "still on oil? the heat pump is €X/mo of your saving" / "going to the full bundle lands +€Y/mo"
  (§6.4) — sourced from `Recommendation.upsell` (prose from F16).
- Loading skeletons; empty/initial state; error fallback; accessible disclosure widgets + highlighted card.

**Out of scope** (explicitly, to prevent creep)
- The **engine** that computes the buckets/optimiser/up-sell diff → **F10** (and **F16** for the up-sell prose);
  F22 only **reads and arranges** them.
- The hero number + honest curve → **F21**; the four toggle rows → **F20**; confidence/assumptions/proposal/CTA → **F23**.
- The Claude German rationale paragraph → **F23** (this feature shows only the short up-sell *line*).
- Any price/SCOP/autarky computation — these arrive in the payload (§7, §12).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | Render **three bucket tiles** — Electricity / Heating / Mobility €/mo — from the selected rung's `breakdown`. | §9, §14.1 |
| R2 | Each tile **expands to "why"**: Electricity = self-consumption %; Heating = SCOP (Case-B efficiency delta if applicable); Mobility = off-peak/home charging. | §9, §7, §5 |
| R3 | Render **scenario cards** for the **four ladder rungs** (`alternatives[]`), each with its `monthly_saving_eur`. | §6.1, §9, D3 |
| R4 | **Highlight the recommended rung** (`Recommendation.best` / the max-net rung from the optimiser). | §6.4 |
| R5 | Render the **inline up-sell line** from `Recommendation.upsell` (`Upsell{reason_md, delta_eur_month, from_scenario_id, to_scenario_id}`) — `reason_md` names the still-burned fuel, `delta_eur_month` is the +€/mo. | §6.4 |
| R6 | The buckets reflect the **currently selected** configuration (kept in sync with F20/F21); switching a scenario card updates the selection. | §6.2, §9 |
| R7 | All figures are **read from the payload**; F22 computes none (the cumulative-interaction story §6.2 is shown, not recomputed). | §14.1, §6.2 |

## 4. Data, formulas & sources

> No hard-coded prices. Bucket €/mo, scenario savings, and the up-sell diff all arrive in `Recommendation`
> (engine F10/F16 → `price_catalog` §12). The "why" figures (autarky %, SCOP, blended charge) are payload/
> assumption metadata. This table records the read mapping.

| Quantity / call | Value / source | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `breakdown.electricity_eur_month` | response field | engine F06/F07 (§5.1/§5.2) | `?fixture` §8 | tile · Electricity |
| `breakdown.heating_eur_month` | response field | engine F08 (§5.3) | `?fixture` §8 | tile · Heating |
| `breakdown.mobility_eur_month` | response field | engine F09 (§5.4) | `?fixture` §8 | tile · Mobility |
| Self-consumption % (autarky) | payload/assumption | BSW/HTW (§7, §10) | 0.30 / ~0.60 | Electricity "why" |
| SCOP (new / old Case B) | payload/assumption | BWP/JAZ (§10) | 3.5–4.0 / 2.8 | Heating "why" |
| `Recommendation.upsell{reason_md, delta_eur_month}` | response field (prose + €) | engine F10 + LLM F16 (§6.4) | `?fixture` §8 | up-sell line |

§6.4 optimiser & up-sell, copied verbatim so F22 arranges against one definition:
```
recommend() walks the ladder and returns the rung with the largest monthly_saving (not necessarily the
deepest — a layer whose installment outweighs its saving is skipped). Up-sell = a diff vs the next-smaller
rung, surfaced inline: "Going from PV+battery (−€24/mo) to the full bundle lands +€120/mo — because you're
still burning oil + petrol that the heat pump and EV displace."
```
§6.2 (why a bigger bundle saves more — shown, not recomputed):
```
Later layers raise annual_consumption_kwh, which lifts the self-consumption value of the PV+battery already
installed (Layers 1–2 re-evaluated on the running state). This is why a bigger upgrade can raise the saving.
```

## 5. Contract surface  *(contract_impact = reads)*

- Reads `Recommendation { best, alternatives[], upsell: Upsell{reason_md, delta_eur_month, from_scenario_id,
  to_scenario_id} }` and each `ScenarioResult.breakdown{electricity,heating,mobility}_eur_month` +
  `monthly_saving_eur` from `specs/api/openapi.yaml` (F02). The scenario cards read `alternatives[]`.
- The "why" figures (autarky %, SCOP, blended charge) are read from the payload's assumption/energy-context
  metadata where present; otherwise shown as labelled assumptions.
- New/changed schema objects: none (read-only).
- Backwards-compatible? Yes — read-only; tracks F02.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (three tiles — §8)** — Given the full §8 `Recommendation`, when the dashboard renders, then three
  tiles — **Electricity / Heating / Mobility** — show their `breakdown.*_eur_month` values (§9).
- [ ] **AC2 (expand "why")** — Given the Electricity tile, when expanded, then it shows the **self-consumption %**;
  the Heating tile shows **SCOP** (and the Case-B efficiency delta when the HP is an upgrade); the Mobility tile
  shows **off-peak/home charging** — the §7/§5 drivers (§9).
- [ ] **AC3 (four scenario cards + highlight — §8)** — Given the §8 `alternatives[]`, when the cards render, then
  there are **four** rungs (☀️, ☀️+🔋, ☀️+🔋+♨️, full) each with its `monthly_saving_eur` (the §8 cumulative-net
  path −24 / −24 / −4 / +120), and the **full bundle is highlighted** as `best` (§6.4).
- [ ] **AC4 (up-sell line — §8)** — Given the §8 result, when the up-sell renders, then it states the diff vs the
  next-smaller rung naming the still-burned fuel, e.g. **"PV+battery (−€24/mo) → full bundle +€120/mo — still
  burning oil + petrol"** (the §6.4 example), sourced from `Recommendation.upsell.reason_md` (with `delta_eur_month`).
- [ ] **AC5 (selection sync)** — Given a scenario card is clicked, when it becomes selected, then the buckets,
  hero (F21), and configurator rows (F20) all reflect that rung (one selection, §6.2).
- [ ] **AC6 (honesty/edge — owned/absent bucket)** — Given a household with `NONE` mobility (or an already-owned
  EV+charger so Layer 4 Δ=0), when the tiles render, then the **Mobility** tile shows €0 / "no change" honestly
  (no fabricated mobility saving), consistent with the §3.2 offer matrix.
- [ ] **AC7 (a11y + states)** — Given the tiles/cards, when navigated by keyboard/screen-reader, then each
  disclosure is a labelled expandable control and the highlighted card is programmatically marked as recommended;
  loading shows skeletons; pre-intake shows the empty state; a payload error shows a retry-able fallback.

## 7. Test plan

- **Unit** (component, zero network): tiles map `breakdown.*` to the three values (AC1); the "why" disclosure
  renders autarky/SCOP/charging from metadata (AC2); the recommended-card resolver highlights `best` (AC3);
  the up-sell line renders from `upsell` (AC4); empty/absent buckets render €0/"no change" (AC6).
- **Integration / contract**: with the §8 `?fixture` `Recommendation` (MSW, typed from F02), the four cards
  show the −24/−24/−4/+120 path, the full rung is `best`, and selecting a card propagates to F20/F21 (AC5).
- **Demo-safety**: buckets, scenario cards, and the up-sell line render **offline** from the §8 golden payload
  (mock-first); the up-sell copy matches the payload's `upsell` (no FE-invented number).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F20** (the selected rung + ladder), **F21** (the hero it sits under), **F18** (state,
  `?fixture`, loading/error/empty). The numbers come from **F10** (buckets/optimiser/up-sell diff) and **F16**
  (up-sell prose) on the BE — but F22 is **never blocked**, it reads the `?fixture` §8 payload (mock-first).
- **Downstream (feeds):** the selected scenario informs **F23**'s proposal/CTA (the chosen rung is what gets
  proposed/financed).
- **Mock until ready:** a blocked dev mocks `alternatives[].breakdown` and `upsell` from the frozen contract
  (the §8 breakdown + the §6.4 up-sell example).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Buckets don't reconcile with the headline | Buckets are the selected rung's `breakdown`; the hero is its `monthly_saving_eur` — both from one `ScenarioResult`; AC5 ties selection across F20/F21/F22. |
| Up-sell invents a number | The line is rendered from `Recommendation.upsell` (engine F10 + guarded LLM F16); AC4 asserts it matches the payload — §15. |
| "Why" over-claims certainty | Show autarky/SCOP/spread as labelled drivers (§7); the widest (dynamic-tariff) driver stays on its own line (§7.1). |
| Fabricated saving for an absent category | Absent/owned bucket shows €0/"no change" per the §3.2 matrix; AC6 guards it. |
| Recommended rung mislabeled | Highlight strictly `Recommendation.best` (the optimiser's max-net rung, §6.4); AC3 asserts it. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 four-rung path and the §6.4 up-sell example).
- [ ] Lint + type-check clean (`eslint` + `tsc`).
- [ ] Contract honored — reads `breakdown`/`alternatives[]`/`best`/`upsell` as frozen; no payload drift.
- [ ] No secret added to the frontend bundle (only `VITE_API_BASE_URL`); no hard-coded price (buckets/up-sell from the payload, §12).
- [ ] Every figure traces to the payload or a labelled assumption — F22 arranges, it does not invent.
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path (buckets + scenario cards + the up-sell line under the hero) still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §9 (bucket tiles, scenario comparison, up-sell), §6.4 (optimiser & up-sell diff), §6.2 (cumulative interaction — why bigger saves more), §7/§7.1 (self-consumption, SCOP, dynamic-tariff drivers), §5.1–§5.4 (bucket math behind the "why"), §3.2 (offer matrix for absent/owned categories).
- `specs/api/openapi.yaml` (F02 — `ScenarioResult.breakdown`, `alternatives[]`, `best`, `upsell`) · `specs/domain/savings-engine.spec.md` (F10 optimiser it reads).
- Backlog `FEATURE_BACKLOG.md` §3 E3 row F22, §2 D3 (4 cumulative rungs = `alternatives[]`), §5 (§9/§6.4/§6.2 traceability).
