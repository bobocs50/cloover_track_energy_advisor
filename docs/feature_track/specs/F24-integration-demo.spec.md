---
id: F24
title: End-to-end integration + demo determinism
epic: E4 Integration & Demo
owner: Zhou
co_owners: [Philips]
reviewers: [Lukas]
priority: P4
mvp: true
status: Ready
branch: feat/F24-integration-demo
depends_on: [F17, F22]
contract_impact: reads
estimate_h: 3
---

# F24 — End-to-end integration + demo determinism

> **North-Star link:** makes the one number real on stage — wires the Vite SPA to the FastAPI BFF on
> seeded data so the live configurator shows `monthly_saving` end-to-end, then **freezes** it behind
> `?fixture` golden payloads so the 90-second demo (§9) is byte-stable and rehearsable regardless of
> network or live-API weather.

## 1. Intent (what & why)

F24 is the integration + demo-determinism feature. It connects the frontend (F18–F23) to the backend
(`/recommend` + `/site-check`, F17) running entirely on **seeded offline data** (F04 Supabase seed +
`price_catalog`), locks the `?fixture=<id>` golden payloads so the headline and every layer row
reproduce exactly, exercises **every fallback** (PVGIS→constant 980, SMARD→seeded €0.12 spread,
OSM→checkbox), and makes the **§9 90-second demo path** green, scripted and rehearsed in P4. It implements
the §1 determinism guarantee and the §15 demo-safety mitigations as a runnable checklist.

**Co-ownership:** **Zhou owns the backend side** (`?fixture` payload freeze, offline seed, fallbacks,
endpoint wiring) and **Philips owns the frontend side** (FE↔BE wiring, the demo-path UX, rehearsal feel,
the assumptions-drawer live re-run). **Lukas is the review gate** — he sanity-checks every displayed
number against §8 (€435 baseline → −€24/≈€0/+€20/+€124 rows → +€120 now / €364 after / ±€35) and the
honest behaviours before this is called "done".

## 2. Scope

**In scope**
- Wire the SPA to FastAPI on **seeded data**: `/site-check` then `/recommend` (§14.1, §14.2), states (loading/error) handled.
- **Lock the `?fixture=<id>` golden payloads** on `/recommend` (and `/site-check`) — byte-stable frozen JSON (§1, §15). **Two golden fixtures are committed/captured here**: `demo-detached.json` (the wide ±€35 band — the headline state) and `demo-detached-edited.json` (the tightened band — the assumptions-drawer "edit → band tightens" beat, F23 AC3b). **Both are re-captured from the real engine** (live seed run) **before the video** so the on-stage numbers are real, not hand-pinned.
- Exercise **every fallback** with the live toggles off: PVGIS→**const 980 kWh/kWp**, SMARD→**seeded €0.12/kWh** spread, OSM parking→**user checkbox** (§5.1, §7.1, §4).
- Make the **§9 90-sec demo path** green end-to-end and **rehearse it in P4** (TIMELINE → "The 90-second demo"): address+5 numbers → solar number → tick 🔋 → tick ♨️+🚗 → edit one assumption → "Generate proposal".
- Assert the **honest behaviours** on the path: battery shown **≈€0 honestly**, headline **jumps** on ♨️+🚗 with the up-sell line, **band tightens** on an assumption edit.
- The §15 risk-mitigation **checklist** verified green (seed, `?fixture`, fallbacks, LLM number-assertion, no secret in bundle).
- A scripted rehearsal artifact (the exact keystrokes/clicks + expected on-screen numbers) used at the gate.

**Out of scope** (explicitly, to prevent creep)
- New domain math, layer physics, or financing logic → owned by F05–F11; F24 only **wires and asserts** existing outputs.
- The LLM number-assertion guard implementation → **F16**; F24 only verifies it fires (copy figures == payload).
- Live PVGIS/SMARD/Google Solar/Denkmal-WFS pulls → 🔶 toggles (F13/F14/F15); the demo runs on seed/fallback (TIMELINE → "If behind — cut…").
- README / Loom / pitch deck / repo-public → **F25** (the submission pack); F24 ends at "demo path green + rehearsed".
- Contract changes → none; F24 is `reads`. Any drift found is fixed in the owning feature's PR, not here.

## 3. Functional requirements

| # | Requirement | Source (§ in system_workflow.md) |
|---|-------------|----------------------------------|
| R1 | The SPA calls **`/site-check` first, then `/recommend`** (§14.2); both succeed on seeded data with no live external call. | §14.1, §14.2, §2 |
| R2 | A **`?fixture=<id>` path on `/recommend`** returns a **frozen payload**, identical across runs (byte-stable golden JSON per demo PLZ). | §1, §15 |
| R3 | **PVGIS fallback:** with the live toggle off, `annual_yield = total_kwp × 980` is used and the result is unchanged run-to-run. | §5.1, §11 |
| R4 | **Dynamic-tariff fallback:** with the SMARD toggle off, the **seeded €0.12/kWh** net spread feeds L2 arbitrage / L4 scheduling. | §7.1, §11 |
| R5 | **OSM fallback:** when Overpass is unavailable/ambiguous, the **private-parking checkbox** drives Layer 4's street-only logic. | §4, §5.4 |
| R6 | The four configurator rows render their per-layer **+€/mo and capex**; owned items show "already installed ✓ — no capex" (§9, §6.3). | §9, §6.3 |
| R7 | The headline equals the deepest selected rung's `monthly_saving`, and the per-layer "+€X/mo" is the diff of consecutive rungs (no extra call). | §6.1, §14.1 |
| R8 | **Honest battery:** ticking 🔋 shows **≈ €0/mo** at the bare-load rung (not hidden, not floored) with the "pays off as load grows" note. | §8.1, §9 |
| R9 | **Up-sell jump:** ticking ♨️ then 🚗 raises the headline (to **≈ +€120/mo** on the §8 home) and surfaces the up-sell line vs PV+battery. | §6.4, §8, §9 |
| R10 | **Band tightens on edit:** editing one assumption in the drawer triggers a live re-run and the ±band narrows/shifts. | §7, §9 |
| R11 | **LLM honesty:** the Claude paragraph's figures match the payload (number-assertion guard from F16 holds); no invented number on screen. | §15, §9 |
| R12 | **No secret in the bundle:** the built SPA ships only `VITE_API_BASE_URL`; all keys stay in FastAPI env. | §1, §15 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> F24 computes nothing new — it **wires and asserts** existing outputs. The only "data" it owns are the
> **frozen `?fixture` golden payloads** (snapshots of the F17 response on seeded data) and the fallback
> constants it exercises. No hard-coded prices: the seed reads `price_catalog` (§12) like production.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| Solar yield | PVGIS `PVcalc` (toggle off in demo) | EU JRC (§11) | **const 980 kWh/kWp** | L1 · annual_yield (R3) |
| Dynamic-tariff spread | SMARD/EPEX (toggle off in demo) | SMARD/BNetzA (§11) | **seeded €0.12/kWh** | L2 arbitrage · L4 sched (R4) |
| EV private parking | OSM Overpass (toggle off / ambiguous) | OSM (§11) | **user checkbox** | Site-Check · L4 street-only (R5) |
| Capex & €/kWh | `price_catalog` via `PricingContext` (seeded) | §12 (Destatis/market) | seeded §12 values | all layers · Δ_capex |
| Golden payloads (×2) | `demo-detached.json` (wide ±€35 band) + `demo-detached-edited.json` (tightened band) | — (re-captured from the real engine on seed before the video) | the seed itself | §9 demo determinism (R2); F23 AC3b edit beat |

Key behaviour, copied verbatim from the spec so the implementer wires against one definition:
```
# Demo determinism (§1):
Demo determinism: a `?fixture=<id>` path on `/recommend` returns a frozen payload.
# Demo-safety fallbacks (§15):
Live API flaky in demo → seed reference data + price_catalog; PVGIS/SMARD are toggles; `?fixture` path
LLM hallucinates a number → LLM never computes; assert every figure in the copy matches the payload
Secret leaks via Vite bundle → only `VITE_API_BASE_URL` client-side; all keys in FastAPI
# The 90-sec demo path the ACs must walk (§9):
type address + 5 numbers → solar number appears → tick 🔋 (≈€0, honest) → tick ♨️ + 🚗 (number jumps
with the up-sell line) → edit one assumption → band tightens → "Generate proposal"
```
§8 reference numbers the displayed values must match (Lukas review gate): baseline **€435/mo**; per-layer
**−€24 / ≈€0 / +€20 / +€124**; cumulative **−€24 / −€24 / −€4 / +€120** now; **€80 / €124 / €230 / €364**
after payoff; band **±€35** with self-consumption named as the biggest driver.

## 5. Contract surface  *(if contract_impact ≠ none)*

- **Reads only** — `contract_impact: reads`. F24 consumes the frozen `Recommendation { best, alternatives[], upsell }` and the `/site-check` response (§14.1, §14.2); it adds no field. The `?fixture` query param exists on `/recommend` per §1 (provided by F17); F24 freezes its payloads.
- New/changed schema objects: none.
- Backwards-compatible? Yes — pure integration/assertion. If wiring uncovers a real payload gap, it is fixed in the **owning** feature's PR (F02/F17) and the golden fixture re-frozen in the same commit; F24 never silently diverges.

## 6. Acceptance criteria (testable — these become the tests)

Written to **literally walk the §9 demo script** and assert the honest behaviours. Concrete numbers from §8.

- [ ] **AC1 (fixture determinism, §1)** — Given `/recommend?fixture=demo-detached-3p`, when called twice (and after a restart), then the response is **byte-identical** and the headline is **+€120/mo now / €364 after payoff / ±€35** (the §8 home).
- [ ] **AC2 (FE↔BE on seed, §14)** — Given the SPA pointed at the local FastAPI with all live toggles **off**, when the intake form posts, then `/site-check` then `/recommend` both return 200 from **seeded data only** (no outbound PVGIS/SMARD/OSM/Anthropic call) and the hero number renders.
- [ ] **AC3 (demo step 1 — solar appears, §9)** — Given "address + 5 numbers" entered for the demo PLZ, when submitted, then the **☀️ Solar row shows −€24/mo (€13,050 · 0 % VAT)** and the headline reflects solar-only honestly (≈ −€24/mo, **not floored at 0**).
- [ ] **AC4 (demo step 2 — battery ≈€0 honestly, §8.1/§9)** — Given solar is on, when the user **ticks 🔋**, then the **Battery row shows ≈ €0/mo (€5,600)** with the "break-even now, pays off as load grows" note, and the headline stays ≈ −€24/mo (battery doesn't move it at the bare load).
- [ ] **AC5 (demo step 3 — number jumps on ♨️+🚗, §6.4/§8)** — Given PV+battery, when the user **ticks ♨️ then 🚗**, then the headline **jumps to ≈ +€120/mo now (€364 after payoff)**, the ♨️ row shows **+€20/mo** and the 🚗 row **+€124/mo**, and the **up-sell line** appears ("…still burning oil + petrol that the heat pump and EV displace", +€144/mo vs PV+battery).
- [ ] **AC6 (demo step 4 — band tightens on edit, §7/§9)** — Given the full bundle, when the user **edits one assumption** in the drawer (e.g. roof tilt/azimuth or autarky), then in demo mode the view **swaps to `demo-detached-edited.json`** (the committed tightened-band fixture, F23 AC3b) and the **±band narrows** with **zero** live dependency (assert band width strictly decreases), biggest-driver line still shown; the **live `/recommend` re-run** (debounced) is the "if wifi holds" upgrade.
- [ ] **AC7 (demo step 5 — proposal, §9)** — Given the chosen config, when the user clicks **"Generate proposal"**, then the Claude paragraph (3 sentences, plain German) renders and **every figure in it matches the payload** (F16 guard holds — no invented number).
- [ ] **AC8 (PVGIS fallback)** — Given the PVGIS live toggle **off**, when `/recommend` runs, then yield uses **`total_kwp × 980`** and the solar number is identical run-to-run (no network dependency).
- [ ] **AC9 (SMARD fallback)** — Given the SMARD toggle **off**, when L2/L4 compute, then the **seeded €0.12/kWh** spread is used and the arbitrage line is deterministic.
- [ ] **AC10 (OSM fallback)** — Given Overpass unavailable, when parking is unknown, then the **checkbox** governs: "street-only" hides/limits Layer 4 (Case B hidden; Case A blend rises → saving shrinks honestly), per §5.4.
- [ ] **AC11 (honesty/edge — owned equipment)** — Given a household that **already owns PV at cap (or a modern HP / EV+charger)**, when the configurator renders, then those rows show **"already installed ✓ — no capex"** with **Δ = 0** and the headline is **not inflated** by owned hardware (§3.2, §6.3).
- [ ] **AC12 (no secret in bundle, §15)** — Given a production SPA build, when the bundle is grepped, then it contains **only `VITE_API_BASE_URL`** and **no** Anthropic/Google/Supabase key.

## 7. Test plan

- **Unit** (pure domain only, zero I/O): not the focus of F24 (math is covered by F05–F11). Optionally a golden-payload **snapshot test** asserting the `?fixture` JSON equals the committed §8 reference.
- **Integration / contract**: end-to-end against local FastAPI on seed — `/site-check`→`/recommend` happy path; assert the frozen `Recommendation`/`alternatives[]`/`upsell` against the F02 contract; the three fallbacks (980 / €0.12 / checkbox) toggled and asserted deterministic; the bundle-secret grep (AC12).
- **Demo-safety**: the **§9 90-second path** scripted as an automated/manual walkthrough (e.g. Playwright or a written runbook) producing the exact on-screen numbers (−€24 / ≈€0 / +€20 / +€124 → +€120 / €364 / ±€35); the §15 mitigation **checklist** ticked green; rehearsed at the **P4 gate** (TIMELINE → "The 90-second demo") with Lukas signing off the numbers vs §8.

**§15 demo-safety checklist (must all be green at the gate):**
- [ ] Seeded reference data + `price_catalog` (offline) — no live dependency on the happy path.
- [ ] Both `?fixture` golden payloads (`demo-detached.json` + `demo-detached-edited.json`) frozen, byte-stable, and re-captured from the real engine before the video (AC1, AC6).
- [ ] PVGIS→980, SMARD→€0.12, OSM→checkbox fallbacks exercised (AC8–AC10).
- [ ] LLM number-assertion guard holds — copy figures == payload (AC7, F16).
- [ ] Battery ≈€0 shown honestly; early solar-only ≈ −€24 not floored (AC3, AC4).
- [ ] Owned-equipment never inflates the saving (AC11).
- [ ] No secret in the Vite bundle — only `VITE_API_BASE_URL` (AC12).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F17** (`/recommend` + `/site-check` wired with the `?fixture` param + persistence), **F22** (the FE bucket breakdown + scenario cards + up-sell line — the deepest UI consumer), and transitively F18–F23 (shell/intake/configurator/hero/drawer/proposal), F04 (offline seed + `price_catalog`), F16 (LLM guard). F03 §8 numbers as the truth set for the review gate.
- **Downstream (feeds):** **F25** (the submission pack records this exact demo path in the Loom + README run instructions); the live finalist pitch (HACKATHON_MANUAL §Finalist) relies on the rehearsed path.
- **Mock until ready:** while any UI piece lags, the FE wires against the **frozen `?fixture` payload** from the contract (the same golden JSON F24 locks); the demo path can be rehearsed on the fixture before the live seed path is fully green.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Live API flaky on stage | Seed everything (F04) + **`?fixture` golden payloads** (AC1); PVGIS/SMARD/Google are 🔶 toggles, off for the demo — §15. |
| Displayed number drifts from §8 | **Lukas review gate**: every on-screen figure asserted vs §8 (€435 → −€24/≈€0/+€20/+€124 → +€120/€364/±€35) before "done" — §8, TIMELINE → "The 90-second demo". |
| Battery/early-solar number looks implausible | Shown **honestly** (≈€0 / ≈−€24, not floored) with the "pays off as load grows" + break-even note — §8.1, §15. |
| LLM invents a number in the proposal | LLM prose-only + **number-assertion guard** (F16); F24 asserts copy figures == payload (AC7) — §15. |
| Integration left to the end | F24 starts **as soon as F17 returns a fixture** (TIMELINE); mock-first from the frozen contract — §15, FEATURE_BACKLOG §6. |
| Secret leaks via the bundle | Only `VITE_API_BASE_URL` client-side; bundle-grep gate (AC12); all keys in FastAPI — §1, §15. |
| Owned-equipment inflates the saving | §6.3 gating → "already installed ✓", Δ = 0, excluded from the headline (AC11) — §3.2, §15. |
| Demo not rehearsed → fumbled live | Scripted runbook + **P4 rehearsal** owned jointly (Zhou be / Philips fe), Lukas sign-off — TIMELINE → "The 90-second demo". |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass (the §9 path walked, fallbacks + fixture determinism asserted; manual runbook for the UI steps documented).
- [ ] Lint + type-check clean (`ruff`+`mypy` / `eslint`+`tsc`); `main` is green.
- [ ] Contract honored (reads only; no payload drift — any gap fixed in F02/F17 and the fixture re-frozen same-commit).
- [ ] **No secret in the frontend bundle** (grep gate); no hard-coded price (seed reads `price_catalog`).
- [ ] Every on-screen figure traces to the payload / §8 / a labelled assumption — **Lukas number-sanity sign-off recorded** (the review gate).
- [ ] Reviewed by Lukas; co-owners (Zhou be + Philips fe) both signed off; merged to `main`.
- [ ] The **§9 90-second demo happy-path is green and rehearsed** end-to-end on seeded data, and the §15 demo-safety checklist (§7) is fully ticked.

## 11. References

- `docs/design_plan/system_workflow.md` §1 (determinism, no-secrets), §9 (demo flow + 90-sec script), §15 (risks/demo-safety), §6.1–§6.4, §7, §8/§8.1, §14.1/§14.2
- `docs/feature_track/TIMELINE.md` → "The 90-second demo" (the demo path the ACs walk) · → "If behind — cut…" (the cut order that protects the demo)
- `specs/api/openapi.yaml` (`Recommendation`, `alternatives[]`, `upsell`, `?fixture`) · F17 (endpoints), F22 (UI), F16 (LLM guard), F04 (seed)
