# Feature Track — Heimwende Energy Advisor (Cloover track)

This folder is the **project-management layer** for the build. It turns the
[`system_workflow.md`](../design_plan/system_workflow.md) blueprint (the *what*) into the *who / how /
when*, and enforces a **spec-based, contract-first** process so 3 people can build in parallel and
ship a credible demo by **Sun 2026-06-21 14:00**.

> **One product, one number:** `monthly_saving = current_spend − (loan_installment + new_energy_cost)`.
> Four stacked layers: ☀️ Solar → 🔋 Battery → ♨️ Heat pump → 🚗 EV charger.

## Read in this order

1. **[PROCESS.md](./PROCESS.md)** — the spec→branch→build→review→merge loop, git conventions, and the
   7 engineering invariants (LLM never computes · contract-first · no FE secrets · no hard-coded
   prices · pure domain core · honest over precision · demo determinism).
2. **[FEATURE_BACKLOG.md](./FEATURE_BACKLOG.md)** — the canonical breakdown: all 25 features (F01–F25)
   with owners, dependencies, MVP flags, locked decisions (D1–D9) and a full traceability matrix back
   to every `system_workflow.md` section.
3. **[TIMELINE.md](./TIMELINE.md)** — the time track list on an H+offset clock (Sat 18:00 → Sun 14:00,
   ~15 build hours), owner-tagged milestone checklists. Build-phase tiers `P0–P5` in the backlog/specs
   map to its milestones: P0→H+2 · P1→H+5 · P2→H+8 · P3→H+10 · P4→H+17 (freeze) · P5→H+17–20 (submit).
4. **[specs/](./specs/)** — one spec per feature, from **[`_TEMPLATE.spec.md`](./_TEMPLATE.spec.md)**.

## Team & surfaces

| | 🟩 **Lukas** | 🟦 **Zhou** | 🟪 **Philips** |
|--|--------------|-------------|----------------|
| Owns | Pure domain engine + data verification + **review gate** | Backend BFF: FastAPI, adapters, Supabase, **the contract** | Frontend: Vite SPA, configurator, dashboard |
| Features | F03, F05–F11 | F01, F02, F04, F12–F17 | F18–F23 |
| Shared | F24 (integration, +Zhou) · F25 (submission) · review (Lukas) | | F24 (integration, +Philips) |

## Status board  *(update the `status:` in each spec; reflect it here)*

| Milestone (TIMELINE) | Features | 🟩 Lukas | 🟦 Zhou | 🟪 Philips |
|----------------------|----------|----------|---------|-----------|
| **H+2** Foundation · Sat 20:00 | F01–F04 | ☐ F03 ☐ F04(data) | ☐ F01 ☐ F02 ☐ F04 | ☐ contract review |
| **H+5** Vertical slice · Sat 23:00 | F05,F06,F12,F17a,F18,F19 | ☐ F05 ☐ F06 | ☐ F12 ☐ F17a | ☐ F18 ☐ F19 |
| **H+8** 4 layers + UI depth · Sun 02:00 | F07,F08,F09,F13,F14,F15,F20,F21 | ☐ F07 ☐ F08 ☐ F09 | ☐ F13 ☐ F14 ☐ F15 | ☐ F20 ☐ F21 |
| **H+10** Feature-complete MVP · Sun 04:00 | F10,F11,F16,F17,F22,F23 | ☐ F10 ☐ F11 | ☐ F16 ☐ F17 | ☐ F22 ☐ F23 |
| **H+17** Integration & freeze · Sun 11:00 | F24 | ☐ review pass | ☐ F24(be) | ☐ F24(fe) |
| **H+17–20** Video & submission · Sun 11–14:00 | F25 | ☐ accuracy audit | ☐ README/repo | ☐ video/deck |

Legend: ☐ todo · ◐ in-progress · ✅ done. (`status:` in the spec frontmatter is the truth; this board is the glance.)

## Decisions locked (don't re-litigate — see FEATURE_BACKLOG §2)

Germany-only · **Vite SPA** (remove stale Next.js) · nested-ladder MVP · KfW 50 %/30 % · heuristic
autarky MVP · seeded €0.12 spread · OSM+checkbox permits · Claude default ·
⚠️ **financing 5 %/180 mo is a TBC assumption — confirm Cloover's real product (D9)**.

## The bar for "done"

A feature is Done only when its acceptance criteria pass as tests, lint/types are clean, the contract
is honored, **no number lacks a source or a labelled assumption**, Lukas has reviewed it, it's merged
to `main`, and the 90-second demo path still works. See `PROCESS.md` §2.
