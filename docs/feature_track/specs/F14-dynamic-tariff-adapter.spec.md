---
id: F14
title: Dynamic-tariff adapter (SMARD/aWATTar)
epic: E2 Backend & Adapters
owner: Zhou
reviewers: [Lukas]
priority: P2
mvp: false
status: Ready
branch: feat/F14-dynamic-tariff-adapter
depends_on: [F04]
contract_impact: none
estimate_h: 1.5
---

# F14 — Dynamic-tariff adapter (SMARD/aWATTar)

> **North-Star link:** The dynamic tariff is the **heart of the Cloover story** (§7.1) — it is the
> spread the battery arbitrages (L2) and the cheap window the EV charges into (L4), both feeding
> `monthly_saving`. The **seeded €0.12/kWh** keeps that number alive offline.

## 1. Intent (what & why)

Pull **day-ahead** hourly electricity prices from official free sources (**SMARD**, alt **aWATTar**),
compute the net **`dynamic_spread`** the engine consumes, cache it in `cache_dynprice` (TTL 1d), and
fall back to the **seeded €0.12/kWh net spread** on any miss/offline. `mvp: false` because the live
pull is the stretch — the **seed is the MVP**; the live pull is a *visible toggle*. The spread feeds
**F07** battery arbitrage and **F09** EV scheduling (§7.1, §11, §13.2).

## 2. Scope

**In scope**
- Pull day-ahead JSON: **SMARD** `smard.de/app/chart_data/{filter}/{region}/index_hour.json` (primary); **aWATTar** `api.awattar.de/v1/marketdata` (alt) (§7.1, §11).
- Compute `dynamic_spread = mean(priciest N hrs) − mean(cheapest N hrs)` (net usable spread) (§7.1, §5.2).
- Cache in **`cache_dynprice (market_area, day, payload_json, fetched_at)`**, TTL **1 day** (§14.3).
- **Fallback**: on miss/timeout/offline → **seeded €0.12/kWh** net spread, emitted as a labelled assumption (§7.1, §10, §15).
- Live pull is a **visible toggle**; demo default uses the seed (§13.2, §16 D6).

**Out of scope** (explicitly, to prevent creep)
- Battery `arbitrage_value` and EV `home_blended_price` math that *use* the spread → **F07 / F09** (this adapter only supplies `dynamic_spread`).
- Full 8760-h hourly simulation (BDEW H0 + per-hour dispatch) → **stretch** (§13.1 #16, §16 D5).
- The `cache_dynprice` table creation → **F04** (F14 reads/writes rows).
- `effective_consumer_price` modelling of fixed components for an absolute tariff → out of scope; we only need the **spread** (§7.1).

## 3. Functional requirements

| # | Requirement | Source (§) |
|---|-------------|------------|
| R1 | Pull day-ahead hourly prices from SMARD `smard.de/app/chart_data/...index_hour.json` (primary). | §7.1, §11 |
| R2 | Support aWATTar `api.awattar.de/v1/marketdata` as an alternate source (SMARD is the fallback for it). | §7.1, §11 |
| R3 | Compute `dynamic_spread = mean(priciest N hrs) − mean(cheapest N hrs)`. | §7.1, §5.2 |
| R4 | Cache responses in `cache_dynprice` keyed by `(market_area, day)`; TTL **1 day**; serve hits without a network call. | §14.3, §13.2 |
| R5 | On miss/timeout/non-200/offline, fall back to the **seeded €0.12/kWh** net spread and label it. | §7.1, §10, §15 |
| R6 | Live pull is gated behind a toggle; demo default uses the seed (D6). | §13.2, §16 |
| R7 | Adapter performs all I/O; it returns a plain `dynamic_spread` (€/kWh) number to the pure engine. | §2 |

## 4. Data, formulas & sources  *(required for any feature that computes or fetches)*

> No catalog prices here — this adapter returns a **spread** (€/kWh). The seed value €0.12 is the
> documented representative net spread (§7.1/§10); the retail/feed-in prices that bound arbitrage live
> in `PricingContext` (§12) and are applied by F07/F09.

| Quantity / call | Value or endpoint | Official source | Fallback | Used in (layer·step) |
|---|---|---|---|---|
| Day-ahead prices | `smard.de/app/chart_data/{filter}/{region}/index_hour.json` | **SMARD / Bundesnetzagentur** (§11) | aWATTar → seed | L2 arbitrage · L4 EV scheduling |
| Day-ahead (alt) | `api.awattar.de/v1/marketdata` | aWATTar (EPEX day-ahead) (§11) | SMARD → seed | same |
| `dynamic_spread` (net) | mean(priciest N) − mean(cheapest N) | derived from SMARD/EPEX (§7.1) | seeded **€0.12**/kWh | L2 · arbitrage_value; L4 · blended price |
| Cache TTL | **1 day** | §14.3 | — | adapter · `cache_dynprice` |

```
# §7.1 dynamic-tariff model, copied verbatim so there is one definition:
#   SMARD:   https://www.smard.de/app/chart_data/{filter}/{region}/index_hour.json   (Bundesnetzagentur)
#   aWATTar: https://api.awattar.de/v1/marketdata    (DE, free) — EPEX day-ahead
dynamic_spread = mean(price of priciest N hours) − mean(price of cheapest N hours)   # net usable spread
# Uses: Battery (L2) charge cheapest → discharge priciest → arbitrage_value (§5.2);
#       EV (L4) schedule charging into cheapest hours → low blended_charge_price (§5.4).
# MVP: seeded representative spread €0.12/kWh net; live pull is a visible toggle.
# cache_dynprice(market_area, day, payload_json, fetched_at)  -- TTL 1d (§14.3)
```

## 5. Contract surface  *(if contract_impact ≠ none)*

`contract_impact: none`. F14 changes no `openapi.yaml` schema; it produces an internal `dynamic_spread`
that F07/F09 fold into the electricity/mobility buckets (§14.1). The spread is **always shown on its own
line, never blended into the "certain" buckets** (§7.1) — a UI concern surfaced by F22/F23.

## 6. Acceptance criteria (testable — these become the tests)

- [ ] **AC1 (URL contract)** — Given the live toggle on, when SMARD is requested, then the URL is `smard.de/app/chart_data/{filter}/{region}/index_hour.json`; the aWATTar alt targets `api.awattar.de/v1/marketdata`.
- [ ] **AC2 (spread formula)** — Given a recorded 24h price series and N, when computed, then `dynamic_spread == mean(top-N) − mean(bottom-N)` (±0.001).
- [ ] **AC3 (cache write + hit)** — Given a fresh pull, when it returns, then a `cache_dynprice` row is written with `fetched_at`; a second call the same day returns the cached spread with **no** outbound request.
- [ ] **AC4 (TTL expiry)** — Given a `cache_dynprice` row older than 1d, when requested, then the adapter refetches (or, if offline, falls back) rather than serving stale data.
- [ ] **AC5 (seeded fallback)** — Given SMARD and aWATTar both unreachable, when invoked, then `dynamic_spread == 0.12` €/kWh and a labelled "seeded spread €0.12 (fallback)" assumption is attached — matching the §8.1 arbitrage line.
- [ ] **AC6 (toggle off = offline)** — Given the live toggle off (D6 default), when invoked, then no network call occurs and the seeded €0.12 spread is returned (demo-safe, §13.2).
- [ ] **AC7 (honesty/edge — spread on its own line)** — Given the spread feeds L2/L4, when the result is assembled, then it is tagged as the **widest-band** input kept on its own line, never merged into the certain buckets (§7.1).

## 7. Test plan

- **Unit** (parser + spread + fallback, no live net): AC2 against a recorded SMARD/aWATTar fixture, AC5/AC7 fallback + banding; the §8.1 `€0.12 spread` as a named vector feeding the battery's +€259/yr arbitrage line.
- **Integration / contract**: cache round-trip against seeded `cache_dynprice` (AC3/AC4); assert the returned shape is the bare `dynamic_spread` F07/F09 expect.
- **Demo-safety**: toggle off → zero network; seeded €0.12 reproduces the arbitrage figure offline; live SMARD is a `?fixture`-safe visible toggle (F24, §15, §16 D6).

## 8. Dependencies & interfaces

- **Upstream (needs):** **F04** (`cache_dynprice` table + the seeded €0.12 source row), FastAPI env (no key — SMARD/aWATTar keyless, §11).
- **Downstream (feeds):** **F07** (battery `arbitrage_value`), **F09** (EV `home_blended_price` scheduling), **F17** (pipeline toggles the live pull), **F11** (the widest-band line, §7).
- **Mock until ready:** F07/F09 mock this by injecting `dynamic_spread = 0.12`; swap to live/cached when F14 merges.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Live SMARD/aWATTar flaky on stage | Seeded €0.12 fallback (AC5) + 1d cache + `?fixture`; toggle defaults off (D6, §13.2, §15). |
| Spread blended into "certain" buckets → over-claim | Arbitrage kept on its own widest-band line (AC7, §7.1). |
| Stale cached spread | TTL 1d enforced; expiry refetches/falls back (AC4, §14.3). |
| SMARD filter/region or aWATTar schema drift | Defensive parse; on parse failure → seeded fallback, never crash (§15). |

## 10. Definition of Done (checklist)

- [ ] All acceptance criteria pass as automated tests (URL, spread, cache hit/expiry, seeded fallback).
- [ ] Lint + type-check clean (`ruff` + `mypy`).
- [ ] Contract honored — `contract_impact: none`; no `openapi.yaml` change.
- [ ] No secret in the frontend bundle (SMARD/aWATTar keyless); no hard-coded price.
- [ ] Every figure traces to a source (SMARD/EPEX) or a labelled assumption (€0.12 seed).
- [ ] Reviewed by Lukas; merged to `main`; main is green.
- [ ] Demo happy-path still works **offline** (toggle off / seeded spread) after merge.

## 11. References

- `docs/design_plan/system_workflow.md` §7.1 (dynamic-tariff model, SMARD/aWATTar URLs, €0.12 seed), §5.2 (arbitrage uses the spread), §5.4 (EV scheduling), §11 (sources, keyless), §14.3 (`cache_dynprice` TTL 1d), §10 (spread constant), §13.2 (offline selection), §15 (flaky-API), §16 D6 (seeded vs live toggle).
- Backlog `FEATURE_BACKLOG.md` §3 E2 row F14 (✅ seed), §5 §7.1/§11 traceability, §2 D6.
- `specs/api/openapi.yaml` (F02) — unaffected; consumers are F07/F09.
