---
id: F13
title: PVGIS irradiance adapter
epic: E2 Backend & Adapters
owner: Zhou
reviewers: [Lukas]
priority: P2
mvp: false
status: Ready
branch: feat/F13-pvgis-adapter
depends_on: [F12]
contract_impact: none
estimate_h: 1.5
---

# F13 — PVGIS irradiance adapter

> **North-Star link:** PVGIS sharpens the **local-irradiance** certainty driver (§7) behind the Layer 1
> yield that feeds `monthly_saving`. The **constant-980 fallback** keeps that number alive offline, so
> the headline never depends on a live call.

## 1. Intent (what & why)

Fetch the **annual PV yield** for a site from the official EU JRC **PVGIS PVcalc** endpoint and inject
`annual_yield_kwh` into Layer 1 (F06). Results are cached in `cache_pvgis` (TTL 30d); on any miss,
timeout, or offline run the adapter falls back to the **constant `total_kwp × 980`** value the engine
already accepts. `mvp: false` because the *live* call is the stretch — the **fallback is the MVP and
ships as part of F06**; this adapter is the toggle that upgrades it (§5.1, §11, §14.3, §13.2).

## 2. Scope

**In scope**
- Build + issue the PVcalc GET with params `peakpower=<total_kwp>, loss=14, mountingplace=building, angle=<tilt|35>, aspect=<azimuth|0>, outputformat=json` (§5.1, §11).
- Parse `outputs.totals.fixed.E_y` → `annual_yield_kwh` (includes PR/losses) (§5.1).
- Cache in **`cache_pvgis (lat, lon, tilt, azimuth, kwp, payload_json, fetched_at)`**, TTL **30d**; serve cache-hits without a network call (§14.3).
- **Fallback**: on miss/timeout/offline → `annual_yield_kwh = total_kwp × specific_yield` (980 default), emitted with a labelled "specific yield 980 (fallback)" assumption (§5.1, §10).
- Live PVGIS is a **visible toggle**; default demo path uses the fallback/seed (§13.2, §16).

**Out of scope** (explicitly, to prevent creep)
- The Layer 1 self-consumption/feed-in math that *uses* `annual_yield_kwh` → **F06** (this adapter only supplies the number).
- Roof geometry / `usable_roof_m2` precision (Google Solar) → **stretch** (PVGIS + area heuristic for the demo, §11, §13.2).
- The `cache_pvgis` table creation → **F04** (F13 reads/writes rows).
- Coordinate resolution (`lat/lon`) → **F12** (injected into this adapter).

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | Call `GET re.jrc.ec.europa.eu/api/v5_2/PVcalc` with the exact params (loss=14, mountingplace=building, angle, aspect, peakpower, outputformat=json). | §5.1, §11 |
| R2 | Extract `annual_yield_kwh = outputs.totals.fixed.E_y`. | §5.1 |
| R3 | Cache responses in `cache_pvgis` keyed by `(lat, lon, tilt, azimuth, kwp)`; TTL **30 days**. | §14.3 |
| R4 | On cache-hit within TTL, return cached yield with **no** network call. | §14.3, §13.2 |
| R5 | On miss/timeout/non-200/offline, fall back to `total_kwp × 980` and label the assumption. | §5.1, §10, §15 |
| R6 | Live PVGIS is gated behind a toggle/flag; demo default does not require it. | §13.2, §16 |
| R7 | Adapter performs all I/O; it returns a plain `annual_yield_kwh` number to the pure engine. | §2 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> No prices here — this adapter returns a physical yield. The €/kWh that values it lives in
> `PricingContext` (§12) and is applied by F06.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| Annual yield | `GET re.jrc.ec.europa.eu/api/v5_2/PVcalc?...&outputformat=json` → `outputs.totals.fixed.E_y` | **EU JRC PVGIS** (§11) | `total_kwp × 980` | L1 · annual_yield |
| Specific PV yield (DE) | 980 kWh/kWp | PVGIS (§10) | const **980** | L1 · fallback yield |
| Tilt / azimuth defaults | angle **35**, aspect **0** | §5.1 | 35 / 0 | L1 · PVcalc params |
| Cache TTL | **30 days** | §14.3 | — | adapter · `cache_pvgis` |

```
# §5.1 PVGIS call + fallback, copied verbatim so there is one definition:
GET https://re.jrc.ec.europa.eu/api/v5_2/PVcalc?lat=..&lon=..&peakpower=<total_kwp>
    &loss=14&mountingplace=building&angle=<tilt|35>&aspect=<azimuth|0>&outputformat=json
→ annual_yield_kwh = outputs.totals.fixed.E_y            # includes PR/losses
Fallback: annual_yield_kwh = total_kwp × specific_yield(PLZ)   # ≈980 kWh/kWp DE
# cache_pvgis(lat, lon, tilt, azimuth, kwp, payload_json, fetched_at)  -- TTL 30d (§14.3)
```

## 5. Contract surface  *(if contract_impact ≠ none)*

`contract_impact: none`. F13 changes no `openapi.yaml` schema; it produces an internal
`annual_yield_kwh` that F06 folds into `breakdown.electricity_eur_month` (§14.1).

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (URL contract)** — Given `lat/lon/total_kwp/tilt/azimuth`, when the request is built, then it targets `re.jrc.ec.europa.eu/api/v5_2/PVcalc` with `loss=14`, `mountingplace=building`, `outputformat=json`, and the supplied `peakpower/angle/aspect` (defaults 35/0).
- [ ] **AC2 (parse E_y)** — Given a recorded PVcalc JSON, when parsed, then `annual_yield_kwh == outputs.totals.fixed.E_y`.
- [ ] **AC3 (cache write + hit)** — Given a fresh fetch, when it returns, then a `cache_pvgis` row is written with `fetched_at`; a second call within 30d returns the cached value with **no** outbound request.
- [ ] **AC4 (TTL expiry)** — Given a `cache_pvgis` row older than 30d, when requested, then the adapter refetches (or, if offline, falls back) rather than serving stale data.
- [ ] **AC5 (fallback path)** — Given PVGIS is unreachable/times out and `total_kwp=9`, when invoked, then `annual_yield_kwh == 9×980 == 8820` and a labelled "specific yield 980 (fallback)" assumption is attached — matching the §8 PV-yield input.
- [ ] **AC6 (toggle off = offline)** — Given the live toggle is off, when invoked, then no network call occurs and the fallback/seed yield is returned (demo-safe, §13.2).
- [ ] **AC7 (honesty/edge — bad payload)** — Given a 200 response missing `outputs.totals.fixed.E_y`, when parsed, then the adapter does **not** crash; it falls back to 980 and labels the assumption (§15).

## 7. Test plan

- **Unit** (URL builder + parser + fallback, no live net): AC1 param assembly, AC2 parse against a recorded fixture, AC5/AC7 fallback; the §8 `9 kWp → 8,820 kWh` fallback as a named vector.
- **Integration / contract**: cache round-trip against seeded `cache_pvgis` (AC3/AC4); assert the returned shape is the bare `annual_yield_kwh` F06 expects.
- **Demo-safety**: toggle off → zero network; recorded-fixture replay so a live PVGIS outage never breaks the demo (`?fixture` golden path via F24, §15).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F12** (`lat/lon`, `total_kwp`, tilt/azimuth, `specific_yield` fallback), **F04** (`cache_pvgis` table), FastAPI env (no key required — PVGIS is keyless, §11).
- **Downstream (feeds):** **F06** (Layer 1 consumes `annual_yield_kwh`), **F17** (pipeline toggles the live call), **F11** (irradiance band, §7).
- **Mock until ready:** F06 mocks this by injecting `annual_yield_kwh = total_kwp × 980`; swap to the live/cached value when F13 merges.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Live PVGIS flaky on stage | Constant-980 fallback (AC5) + 30d cache + `?fixture` golden payload; toggle defaults off (§13.2, §15). |
| Malformed/changed PVGIS payload | Defensive parse; missing `E_y` → fallback, never crash (AC7, §15). |
| Stale cached yield | TTL 30d enforced; expiry refetches/falls back (AC4, §14.3). |
| Yield over-precision implies false certainty | Fallback is a **labelled** 980 assumption; irradiance shown with ±8 % band in F11 (§7). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (URL, parse, cache hit/expiry, fallback).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored — `contract_impact: none`; no `openapi.yaml` change.
- [ ] No secret in the frontend bundle (PVGIS keyless; no key added anywhere); no hard-coded price.
- [ ] Every figure traces to a source (PVGIS) or a labelled assumption (980 fallback).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works **offline** (toggle off / fallback) after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §5.1 (PVcalc call + 980 fallback), §11 (PVGIS source, keyless), §14.3 (`cache_pvgis` TTL 30d), §10 (specific yield 980), §13.2 (offline/no-key selection), §7 (irradiance certainty), §15 (live-API flaky), §16 (PVGIS toggle).
- Backlog `FEATURE_BACKLOG.md` §3 E2 row F13 (✅ fallback), §5 §5.1/§11 traceability.
- `specs/api/openapi.yaml` (F02) — unaffected; consumer is F06.
