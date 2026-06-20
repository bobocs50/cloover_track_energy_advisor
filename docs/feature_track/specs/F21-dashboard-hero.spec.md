---
id: F21
title: Dashboard hero — the number + honest curve
epic: E3 Frontend
owner: Philips
reviewers: [Lukas]
priority: P2
mvp: true
status: Ready
branch: feat/F21-dashboard-hero
depends_on: [F18]
contract_impact: reads
estimate_h: 2.5
---

# F21 — Dashboard hero — the number + honest curve

> **North-Star link:** this **is** the headline. F21 puts `monthly_saving` in the biggest text on the page
> and tells the truth about it with the two-phase curve (≈ cost-neutral while financing → larger after
> payoff) and the before/after line. The whole product exists to make this one number unmissable and honest
> — **lead the demo with it** (§9).

## 1. Intent (what & why)

Render the dashboard hero from §9: the **biggest-text €/month number** that recomputes as layers toggle,
and the **honest two-phase curve** — savings **while financing** vs **after payoff**, with the **break-even**
month marked — so the number is never overstated. Add the **before/after line** ("Today €435/mo → with the
bundle €Z/mo") and the plain-language honesty caption ("≈ cost-neutral early → €364/mo after payoff"). This
is the trust-builder; the demo opens on it. F21 reads `Recommendation` from the F18 state (mock-first against
the §8 golden payload) and recomputes nothing. Refs §9.

## 2. Scope

**In scope**
- **The hero number**: `monthly_saving_eur` of the current selection, in the largest type on the page; updates
  live as F20 toggles change the selected rung.
- **Honest two-phase curve** (chart): a **while-financing** phase (≈ cost-neutral / small early saving) and an
  **after-payoff** phase (the larger gross saving), with the **break-even month** marked on the timeline (§6.5,
  §9). Both phases visible — never just the rosy after-payoff figure.
- **Before/after line**: "Today €435/mo → with the bundle €Z/mo" (current spend → spend with the bundle), §9.
- **Honesty caption**: "≈ cost-neutral early → €364/mo after payoff" + the break-even year, derived from
  `monthly_saving_eur` / `saving_after_payoff_eur` / `break_even_month` (§6.5).
- Loading skeleton for the hero/curve; empty/initial (pre-intake) state; error fallback; accessibility for the
  number and the chart.

**Out of scope** (explicitly, to prevent creep)
- The financing/break-even **math** (annuity, `saving_after_payoff`, `break_even_month`) → engine **F11**; F21
  only **renders** these payload fields.
- The four layer rows / toggles → **F20** (F21 reads the resulting selection).
- Bucket tiles, scenario cards, the up-sell line → **F22**; confidence chip, assumptions drawer, proposal, CTA → **F23**.
- Any price/subsidy logic — values arrive in the payload (§12, §6.5).

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | The **€/month saving is the biggest text** on the page and recomputes as the selection (F20) changes. | §9 |
| R2 | Show an **honest two-phase curve**: while-financing (≈ cost-neutral) vs after-payoff (larger), **break-even marked**. | §6.5, §9 |
| R3 | The curve must **not** show only the after-payoff figure; the early ≈0/negative phase is visible and labelled honestly. | §8, §8.1, §15 |
| R4 | Show a **before/after line**: "Today €<`current_monthly_spend_eur`>/mo → with the bundle €<Z>/mo" (baseline from the payload, not intake). | §9 |
| R5 | Show the honesty caption "≈ cost-neutral early → €<`saving_after_payoff_eur`>/mo after payoff" + the break-even year from `break_even_month`. | §6.5, §9 |
| R6 | All hero figures are **read from `Recommendation`** (`monthly_saving_eur` + `saving_after_payoff_eur` + `break_even_month` + `current_monthly_spend_eur`); F21 computes none. | §14.1, §6.5 |
| R7 | The hero is the **first/lead** element of the dashboard (demo opens here). | §9 |

## 4. Data, formulas & sources

> No hard-coded prices. The hero number, the after-payoff value, and the break-even all arrive in
> `Recommendation` (engine F11 → `price_catalog` §12). F21 renders; it does not compute. This table records
> which payload fields feed which hero element.

| Quantity / call | Value / source | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| `monthly_saving_eur` (selected rung) | response field (North Star) | engine F11 (§6.5) | `?fixture` §8 (+€120) | hero · big number |
| `saving_after_payoff_eur` (= gross) | discrete response field | engine F11 (§6.5) | `?fixture` §8 (€364) | curve · after-payoff phase |
| `break_even_month` | discrete response field | engine F11 (§6.5) | `?fixture` §8 | curve · break-even marker |
| `current_monthly_spend_eur` | response field (from the payload) | §8 (€435 baseline) | `?fixture` §8 (€435) | before/after line |

§6.5 honest-number definitions, copied verbatim so F21 renders against one definition:
```
monthly_saving      = gross_saving − installment        # North Star (honest: may be ≈0/neg early)
saving_after_payoff = gross_saving
break_even_month    = first month cumulative_net ≥ 0
```
§9 dashboard sketch the hero reproduces faithfully:
```
YOUR SAVING: €X / month            ← biggest text; recomputes as layers toggle
TOTAL  +€120/mo now  →  €364/mo after payoff   ±€35
"≈ cost-neutral early → €364/mo once the loan is paid off"  + break-even year
Today €435/mo → with the bundle €Z/mo
```

## 5. Contract surface  *(contract_impact = reads)*

- Reads `Recommendation.current_monthly_spend_eur` (the before/after baseline comes **from the payload**, not
  echoed from intake) and the selected `ScenarioResult`: `monthly_saving_eur`, `installment_eur_month`, the
  discrete `saving_after_payoff_eur` and `break_even_month` (the honest curve), plus `payback_note` for the
  caption — all from `specs/api/openapi.yaml` (F02).
- New/changed schema objects: none — F02 is frozen and carries `current_monthly_spend_eur`,
  `saving_after_payoff_eur` and `break_even_month` as discrete fields (no `payback_note` parsing needed).
- Backwards-compatible? Yes — read-only.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (big number — §8)** — Given the full §8 `Recommendation`, when the dashboard loads, then **"€120 /
  month"** (≈ +€120) is rendered as the **largest text** on the page (§9).
- [ ] **AC2 (recomputes on toggle)** — Given the hero, when F20 un-ticks ♨️+🚗 (battery rung selected), then the
  hero number updates to the battery rung's `monthly_saving_eur` (≈ the §8 −€24 cumulative) — live, no reload.
- [ ] **AC3 (honest two-phase curve — §8)** — Given the §8 result, when the curve renders, then it shows a
  **while-financing** phase ≈ cost-neutral (+€120) and a distinct **after-payoff** phase at **≈ €364/mo**, with
  a **break-even marker** on the timeline (§6.5, §9).
- [ ] **AC4 (before/after — §8)** — Given `current_monthly_spend_eur` = €435/mo (from the payload), when the
  before/after line renders, then it reads **"Today €435/mo → with the bundle €Z/mo"** with Z = €435 − €120 =
  **€315/mo** (payload baseline minus the saving).
- [ ] **AC5 (honesty caption)** — Given the §8 result, when the caption renders, then it reads "≈ cost-neutral
  early → **€364/mo** after payoff" (from `saving_after_payoff_eur`) and names the break-even year (from `break_even_month`).
- [ ] **AC6 (honesty/edge — solar-only negative shown truthfully)** — Given **solar only** (the §8 −€24 rung),
  when the hero+curve render, then the number is shown as **−€24/mo** (not floored to 0) and the curve's early
  phase is clearly the negative/cost-neutral one with `saving_after_payoff_eur ≈ €80/mo` after payoff (§8.1, §15).
- [ ] **AC7 (a11y + states)** — Given the hero, when read by a screen-reader, then the big number has an
  accessible label (e.g. "your saving: 120 euros per month") and the chart has a text alternative / data table;
  loading shows a hero skeleton; pre-intake shows the empty state; a payload error shows a retry-able fallback.

## 7. Test plan

- **Unit** (component, zero network): the hero renders `monthly_saving_eur` as the largest element (AC1); the
  before/after computes `current_spend − saving` for display (AC4, a pure subtraction of payload values); the
  caption maps `saving_after_payoff_eur`/`break_even_month` to the honest string (AC5); negative saving renders unfloored
  (AC6).
- **Integration / contract**: with the §8 `?fixture` `Recommendation` (MSW, typed from F02), the hero+curve+lines
  render the +€120 / €364 / €435 figures; toggling the selection (F20) re-reads the rung and updates the number (AC2).
- **Demo-safety**: the hero renders the §8 numbers **offline** from the golden payload (mock-first); the two-phase
  curve and break-even are deterministic for the demo open.

## 8. Dependencies & interfaces

- **Upstream (needs):** **F18** (TS client, `Recommendation` state, `?fixture`, loading/error/empty); the
  selected rung from **F20**; the financing/break-even/after-payoff fields produced by **F11** (BE) — but F21 is
  **never blocked**, it renders the `?fixture` §8 payload (mock-first).
- **Downstream (feeds):** sets the visual anchor the rest of the dashboard sits under; **F23**'s confidence chip
  (±€) and CTA attach to this hero; **F22** sits below it.
- **Mock until ready:** a blocked dev mocks `monthly_saving_eur`/`saving_after_payoff_eur`/`break_even_month` from the
  frozen contract (the §8 +€120 / €364 / break-even fixture).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Number overstated → trust lost | Two-phase curve shows the **honest** early phase + break-even (§6.5, §9); after-payoff is never the headline; AC3/AC6 guard it. |
| Battery/solar ≈0 or negative looks broken | Render unfloored with the honest caption (§8.1); AC6 asserts −€24 is shown, not hidden. |
| Hero drifts from the configurator total | F21 reads the **same** selected `alternatives[]` rung as F20 (one source); AC2 ties them together. |
| Chart inaccessible | Text alternative / data table + accessible big-number label (AC7) — §9 honesty must be perceivable. |
| Live API flaky on the demo open | `?fixture` golden payload renders the §8 hero offline; error state offers retry — §1, §15. |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (incl. the §8 +€120 / €364 / €435 / break-even vectors).
- [ ] Lint + type-check clean (`eslint` + `tsc`).
- [ ] Contract honored — reads the frozen `monthly_saving_eur` / `saving_after_payoff_eur` / `break_even_month` / `current_monthly_spend_eur`; no contract change needed (F02 is frozen).
- [ ] No secret added to the frontend bundle (only `VITE_API_BASE_URL`); no hard-coded price (all figures from the payload, §12).
- [ ] Every figure traces to the payload or a labelled assumption — the hero renders, it does not invent precision.
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] The demo happy-path (the big number + honest curve lead the dashboard) still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §9 (dashboard hero, the big number, honest curve, before/after, the sketch), §6.5 (monthly_saving / saving_after_payoff / break_even_month), §8 / §8.1 (worked example, honest early ≈0/negative), §15 (don't overstate the number).
- `specs/api/openapi.yaml` (F02 — `ScenarioResult.monthly_saving_eur`, `saving_after_payoff_eur`, `break_even_month`, `Recommendation.current_monthly_spend_eur`) · `specs/domain/savings-engine.spec.md` (F11 financing it renders).
- Backlog `FEATURE_BACKLOG.md` §3 E3 row F21 (the big €/month number + honest two-phase curve), §5 (§9 traceability).
