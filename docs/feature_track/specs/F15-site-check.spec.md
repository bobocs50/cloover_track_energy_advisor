---
id: F15
title: Site-Check adapter (permits & feasibility)
epic: E2 Backend & Adapters
owner: Zhou
reviewers: [Lukas]
priority: P2
mvp: true
status: Ready
branch: feat/F15-site-check
depends_on: [F12]
contract_impact: reads
estimate_h: 1.5
---

# F15 — Site-Check adapter (permits & feasibility)

> **North-Star link:** Site-Check *defends* `monthly_saving` by confirming the upgrades are legally and
> physically feasible (so the saving is real) — and its **street-only-parking** flag honestly shrinks
> the Layer 4 saving rather than inflating it (§4, §5.4).

## 1. Intent (what & why)

Implement the §4 pre-step: given the **full address** (street + house no, mandatory), produce the
permit/obligation picture and feasibility flags. In 2026 German law *privileges* renewables — roof-PV,
air-source HP and wallboxes are **verfahrensfrei** — so this is a fast **feasibility + obligations**
check, **not a gate** (§4). Returns the typed `SiteCheckResponse{roof_ok, feasibility_flags: FeasibilityFlag[], energy_context: EnergyContext, assumptions: Assumption[]}`.
**MVP-lite = green checks + the one real gate** (Denkmal). OSM Overpass supplies parking; MaStR seed
supplies neighbour-count social proof (§4, §14.2).

## 2. Scope

**In scope**
- The §4 permit/obligation table, hardcoded national rules: PV **verfahrensfrei** 🟢; **GEG always-compliant** 🟢 (§71); **WEG §20 / BGB §554 EV right** 🟢; grid-registration notices (wallbox ≤11 kW notify / >11 kW approval; battery **MaStR within 1 month**) ℹ️ (§4).
- **Denkmalschutz (heritage) = the only real gate**: `denkmal_seed`/checkbox → 🟢 not listed / 🟡 listed → approval (§4).
- **OSM Overpass** parking (`overpass-api.de/api/interpreter`) + user checkbox → private (driveway/garage) 🟢 vs street-only 🟡 (public-charge fallback) (§4, §11).
- **MaStR neighbour-count** seed (by PLZ) → social proof 🟢 40+ / 🟡 5–40 / ⚪ unknown (§4).
- HP advisories: old-boiler **opportunity** (`heating ∈ {OIL,GAS}`) ℹ️; outdoor-unit noise (TA Lärm ~3 m) 🟢/🟡 (§4).
- Output the typed `SiteCheckResponse{roof_ok, feasibility_flags: FeasibilityFlag[]{product,check,status,message}, energy_context: EnergyContext, assumptions: Assumption[]}` per §14.2.

**Out of scope** (explicitly, to prevent creep)
- The Layer 3/4 economics that *consume* these flags (street-only blend, KfW) → **F08/F09/F11** (Site-Check only sets the flag).
- Live **Denkmalschutz WFS** (Bavaria) → **stretch** (national checkbox is the MVP fallback, §4, §16 D7).
- Roof-geometry precision (Google Solar `usable_roof_m2`) → **stretch**; `roof_ok` here is the feasibility boolean, not panel layout (§11, §13.2).
- `lat/lon` resolution → **F12** (injected).

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | PV building permit → 🟢 verfahrensfrei (LBO roof-PV), national hardcoded rule. | §4 |
| R2 | Denkmal (heritage) is the **only real gate**: `denkmal_seed`/checkbox → 🟢 not listed / 🟡 listed→approval. | §4 |
| R3 | MaStR neighbour count (seed by PLZ) → 🟢 40+ / 🟡 5–40 / ⚪ unknown (social proof, never gates). | §4 |
| R4 | Heat pump → 🟢 GEG-compliant always (§71); old-boiler ℹ️ opportunity if `heating ∈ {OIL,GAS}`; noise 🟢/🟡. | §4 |
| R5 | EV right-to-install 🟢 (WEG §20 / BGB §554); parking via OSM Overpass + checkbox → 🟢 private / 🟡 street-only. | §4, §11 |
| R6 | Grid-registration notices ℹ️: wallbox ≤11 kW notify / >11 kW approval; battery register in MaStR within 1 month. | §4 |
| R7 | Return the typed `SiteCheckResponse{roof_ok, feasibility_flags: FeasibilityFlag[], energy_context: EnergyContext, assumptions: Assumption[]}`; never block the result (degrade to checkbox/⚪). | §14.2, §3.4 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> No prices computed here — Site-Check yields **flags + context**. Each flag cites its national legal
> source; data gaps fall back to a **checkbox** or ⚪ unknown, never a gate.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| PV permit | verfahrensfrei | LBO (roof-PV) (§4) | hardcoded rule | Site-Check · solar 🟢 |
| Heritage gate | `denkmal_seed` / checkbox | Länder Denkmal datasets; Bavaria WFS (§4, §11) | **user checkbox** | Site-Check · solar/HP gate |
| Neighbour precedent | `mastr_seed` count by PLZ | MaStR Gesamtdatenexport (§4, §11) | ⚪ unknown | Site-Check · social proof |
| EV parking | `overpass-api.de/api/interpreter` | **OSM Overpass** (§11) | **user checkbox** | L4 · private vs street-only |
| GEG compliance | always ≥65 % renewable HP | GEG §71 (§4) | hardcoded | L3 · 🟢 compliant |
| EV right | legal right to install | WEG §20 / BGB §554 (§4) | hardcoded | L4 · 🟢 right |
| Grid registration | ≤11 kW notify / >11 kW approval; battery MaStR ≤1 mo | hardcoded notice (§4) | hardcoded | L2/L4 · ℹ️ notice |

```
# §4 result logic (national, copied for one definition):
PV permit            → 🟢 verfahrensfrei (LBO)
Denkmal              → 🟢 not listed | 🟡 listed → approval        # ← only real gate; checkbox fallback
MaStR neighbours     → 🟢 40+ | 🟡 5–40 | ⚪ unknown               # social proof only, never gates
HP GEG               → 🟢 always compliant (§71); old boiler OIL/GAS → ℹ️ KfW opportunity + timeline
EV right             → 🟢 WEG §20 / §554 BGB; parking OSM+checkbox → 🟢 private | 🟡 street-only (public-charge fallback)
Grid registration    → wallbox ≤11 kW notify / >11 kW approve; battery → register in MaStR ≤1 month
Battery install      → 🟢 indoor, verfahrensfrei
# GEG 2024 timeline (urgency, not a block): municipalities >100k by 30 Jun 2026, rest by 30 Jun 2028.
```

> **Labelled assumption:** Denkmalschutz has **no single national API** and MaStR has **no clean
> count-by-PLZ REST** (§4) — so heritage falls back to a checkbox and neighbour counts are **seeded for
> demo PLZs** (⚪ elsewhere). Both are labelled, and social proof **never gates** the result.

## 5. Contract surface  *(contract_impact = reads)*

- Implements `POST /api/v1/advisor/site-check`, filling the typed `SiteCheckResponse{ roof_ok,
  feasibility_flags: FeasibilityFlag[]{product,check,status,message}, energy_context: EnergyContext{lat,lon,
  specific_yield_kwh_per_kwp,retail_price_eur_kwh,grid_fee_eur_kwh,climate_zone,mastr_neighbour_count},
  assumptions: Assumption[]{field,value,source,editable} }` per §14.2 (the SPA calls it before `/recommend`).
  The wire shape is frozen in the contract (F02); F15 fills it. The endpoint plumbing/CORS/persistence is **F17**.
- New/changed schema objects: none — F02 is frozen and carries `SiteCheckResponse`, `FeasibilityFlag`, `EnergyContext` and `Assumption`.
- Backwards-compatible? yes — fills the frozen typed contract.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (green happy-path)** — Given a non-listed address with a seeded high neighbour count, when site-checked, then `roof_ok == true`, PV 🟢 verfahrensfrei, HP 🟢 GEG, EV 🟢 right, MaStR 🟢 40+, and the only ℹ️ items are grid-registration notices.
- [ ] **AC2 (the one real gate — Denkmal)** — Given the heritage checkbox = listed (or `denkmal_seed` flag set), when site-checked, then `feasibility_flags[]` contains a 🟡 "Denkmalschutz → approval" gate while every other check stays 🟢.
- [ ] **AC3 (street-only parking shrinks L4 honestly)** — Given OSM/checkbox = street-only, when site-checked, then a 🟡 "street-only → public-charge fallback" flag is set, which §5.4 uses to drop the PV share / not offer L4 Case B (the honest-saving path).
- [ ] **AC4 (social proof never gates)** — Given `mastr_count` ⚪ unknown for the PLZ, when site-checked, then social proof is ⚪ and the result is **not** blocked (flags still computed).
- [ ] **AC5 (grid-registration notices)** — Given a wallbox >11 kW (and a battery), when site-checked, then ℹ️ notices read ">11 kW → Netzbetreiber approval" and "battery → MaStR within 1 month".
- [ ] **AC6 (OSM fallback to checkbox)** — Given OSM Overpass is unreachable, when site-checked, then parking degrades to the **user checkbox** (no crash) and an assumption is labelled.
- [ ] **AC7 (honesty/edge — MVP-lite)** — Given the MVP-lite path, when site-checked, then the response is **green checks + the one real flag** only (Denkmal), with `energy_context` and `assumptions[]` populated and no fabricated gate.

## 7. Test plan

- **Unit** (flag logic, stubbed OSM/seed): AC1 all-green, AC2 Denkmal gate, AC3 street-only, AC5 grid notices; assert each flag carries its §4 legal source.
- **Integration / contract**: response validates against the frozen typed `SiteCheckResponse` (`FeasibilityFlag[]`, `EnergyContext`, `Assumption[]`) in F02; reads `denkmal_seed`/`mastr_seed`/`reference_plz` from F04; OSM call mocked with a recorded fixture.
- **Demo-safety**: OSM unreachable → checkbox fallback (AC6); seeded Denkmal/MaStR → fully offline; `?fixture` golden Site-Check payload (F24, §15).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F12** (`lat/lon`, `mastr_count`), **F04** (`denkmal_seed`, `mastr_seed`, `reference_plz`), full address from `Household` (F02), FastAPI env (OSM keyless, §11).
- **Downstream (feeds):** **F09** (street-only → L4 blend/offer), **F08** (old-boiler ℹ️ → KfW urgency), **F17** (`/site-check` endpoint), **F23** (permits panel UI).
- **Mock until ready:** F17/F23 mock `{roof_ok:true, feasibility_flags:[…green…], …}` from the frozen `/site-check` fixture until F15 merges.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Denkmal/MaStR not national | Heritage = checkbox fallback; MaStR seeded for demo PLZs (⚪ elsewhere); social proof never gates (AC4, §4, §15). |
| OSM Overpass flaky | Falls back to the user checkbox (AC6); labelled assumption; demo seed offline (§15). |
| Over-claiming feasibility / hiding a gate | Only the **one real gate** (Denkmal) surfaces; street-only honestly shrinks L4 (AC3, §5.4); MVP-lite avoids fabricated gates (AC7). |
| Grid-registration wrong threshold | ≤11 kW notify / >11 kW approval hardcoded from §4; battery MaStR ≤1 month (AC5). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (flags, gate, street-only, fallbacks).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored — fills the F02-frozen typed `SiteCheckResponse` (`FeasibilityFlag[]`, `EnergyContext`, `Assumption[]`); `contract_impact: reads`.
- [ ] No secret in the frontend bundle (OSM keyless); no hard-coded price.
- [ ] Every flag traces to a §4 national legal source or a labelled assumption (checkbox/⚪ seed).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works **offline** (seeded Denkmal/MaStR, checkbox parking) after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §4 (permit/obligation table, GEG timeline, data reality), §14.2 (`/site-check` contract), §11 (OSM/Denkmal/MaStR sources, keyless), §5.4 (street-only → L4), §3.4 (never block), §13.2 (offline selection), §15 (Denkmal/MaStR not national), §16 D7.
- Backlog `FEATURE_BACKLOG.md` §3 E2 row F15 (✅ lite), §5 §4/§14.2 traceability, §2 D7.
- `specs/api/openapi.yaml` (F02 `/site-check`) · F04 (`denkmal_seed`/`mastr_seed`) · F17 (endpoint plumbing).
