---
id: Fxx
title: <concise feature title>
epic: <E0 Foundations | E1 Domain Core | E2 Backend & Adapters | E3 Frontend | E4 Integration & Demo>
owner: <Lukas | Philips | Zhou>
reviewers: [Lukas]            # Lukas reviews every feature; add others if cross-cutting
priority: <P0 | P1 | P2 | P3 | P4 | P5>   # = build phase, see TIMELINE.md
mvp: <true | false>           # false = stretch, cut first if behind
status: Draft                 # Draft → Ready → In-Progress → In-Review → Done
branch: feat/Fxx-<slug>
depends_on: [Fxx, Fyy]        # feature IDs that must be merged (or mockable) first
contract_impact: <none | reads | extends>   # does this touch specs/api/openapi.yaml?
estimate_h: <number>          # rough person-hours
---

# Fxx — <title>

> **North-Star link:** one sentence on how this feature moves, defends, or *explains* the
> headline `monthly_saving`. If it does none of those, it does not belong in the MVP.

## 1. Intent (what & why)

<2–4 sentences. The user/installer outcome this delivers, in plain language. Reference the
exact `system_workflow.md` section(s) this implements, e.g. (§5.1, §6.1).>

## 2. Scope

**In scope**
- <bullet>

**Out of scope** (explicitly, to prevent creep)
- <bullet — push to a later feature/stretch and name it>

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | <testable statement> | §x |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> Every number must cite an **official/primary source** and a **fallback**. No hard-coded prices —
> prices come from `price_catalog` (§12); this table holds only physics/policy constants or the
> formula. If the feature touches no data, write "N/A — pure UI/plumbing".

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| <e.g. specific yield> | PVGIS PVcalc | EU JRC | const 980 kWh/kWp | L1 · annual_yield |

Key formula(s), copied verbatim from the spec so the implementer codes against one definition:
```
<formula>
```

## 5. Contract surface  *(if contract_impact ≠ none)*

- Request/response fields touched in `specs/api/openapi.yaml`:
- New/changed schema objects:
- Backwards-compatible? <yes/no — if no, coordinate the contract bump in the same PR>

## 6. Acceptance criteria (testable — these become the tests)

Written as Given/When/Then so they map 1:1 to test cases. Include at least one **worked-example
assertion** with concrete numbers from §8 where applicable.

- [ ] **AC1** — Given <input>, when <action>, then <observable result with a number/tolerance>.
- [ ] **AC2** — …
- [ ] **AC3 (honesty/edge)** — <the awkward case: ≈0 saving, missing input, owned-equipment, street-only parking, etc.>

## 7. Test plan

- **Unit** (pure domain only, zero I/O): <cases, incl. the §8 worked example as a fixture vector>
- **Integration / contract**: <endpoint or client test; assert payload matches contract>
- **Demo-safety**: <offline seed / `?fixture` path / fallback exercised>

## 8. Dependencies & interfaces

- **Upstream (needs):** <features/artifacts; what shape of input it consumes>
- **Downstream (feeds):** <who consumes this feature's output>
- **Mock until ready:** <how a blocked consumer mocks this — e.g. a fixture from the frozen contract>

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| <risk> | <mitigation — cross-ref system_workflow.md §15 where relevant> |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (or a documented manual check for pure UI).
- [ ] Lint + type-check clean (`ruff`+`mypy` / `eslint`+`tsc`).
- [ ] Contract honored (no undocumented payload drift); `openapi.yaml` updated in the same PR if `extends`.
- [ ] No secret added to the frontend bundle; no hard-coded price (reads `price_catalog`).
- [ ] Every figure traces to a source or a labelled assumption (no invented precision).
- [ ] Reviewed by Lukas (and the contract owner if `contract_impact ≠ none`); merged to `main`; main is green.
- [ ] The demo happy-path still works end-to-end after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §<...>
- `specs/api/openapi.yaml` · `specs/domain/savings-engine.spec.md` (as applicable)
