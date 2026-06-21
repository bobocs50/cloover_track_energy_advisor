# Backend Layers — Philipp's scope

Build order is fixed: each layer computes on the running state of the ones before it.

## Pipeline status (no agentic orchestration — see `goal.md`)

```
1. address confirmed
2. ┌──┴──┐  PARALLEL (slow HTTP, threads)
   solar  permits
3. ladder math  ── DETERMINISTIC, in sequence
   L1 solar → L2 battery → L3 heatpump → L4 ev → financing → scenarios
4. Recommendation  ── all NUMBERS finalised here (source of truth)
5. LLM call  ── reads the finished numbers, writes the German proposal
6. dashboard
```

- [x] **Layer 0 — Site-Check / Permits** — `adapters/site_check.py` + `permit_layer/` (12 live checks, SSE)
- [x] **Layer 1 — Solar** — `solar_layer/` + `electricity_layer.py`, wired into `build_ladder`
- [x] **Layer 2 — Battery** — `electricity_layer.py:battery_arbitrage_value`, wired
- [x] **Layer 3 — Heat Pump** — `heatpump_layer.py:compute_heating_baseline`, wired
- [x] **Layer 4 — EV Charger** — `ev_layer.py`, wired
- [x] **Layer 5 — Subsidy catalog** — `subsidy_layer/catalog.py` → `SubsidyContext`, **now injected into the engine** (KfW rate is data-driven; crawler refresh is the stretch)
- [x] **Recommendation → LLM proposal** — `engine.recommend` → `adapters/llm/`, runs end-to-end (full bundle ≈ €137/mo on the demo household)

---

## Layer 0 — Site-Check (Permits & Feasibility)
**File:** `adapters/site_check.py` · `domain/savings/permit_layer/`
**Status:** ✅ implemented — `run_site_check()` live; `permit_layer` runs 12 checks over SSE

Pre-step before the savings ladder. Validates the address/roof and returns per-product feasibility flags.

| Check | Source | Result |
|-------|--------|--------|
| Solar PV permit | LBO — verfahrensfrei | 🟢 / 🟡 heritage |
| Denkmalschutz | Länder datasets / checkbox | 🟢 / 🟡 listed |
| Neighbour precedent | MaStR by PLZ (seeded) | 🟢 40+ / 🟡 5–40 / ⚪ unknown |
| Heat pump GEG | Hardcoded rule | 🟢 always compliant |
| Heat pump noise | TA Lärm advisory | 🟢 / 🟡 tight plot |
| EV charger right | §20 WEG / §554 BGB | 🟢 legal right |
| EV parking | OSM Overpass + checkbox | 🟢 / 🟡 street-only |
| Battery | Hardcoded | 🟢 indoor, always ok |

Output: `SiteCheckResponse { roof_ok, feasibility_flags[], energy_context, assumptions[] }`

---

## Layer 1 — Solar / PV (Electricity bucket)
**File:** `domain/savings/solar_layer/` (roof + sizing) · `domain/savings/electricity_layer.py` (meter math)
**Status:** ✅ implemented & wired into `build_ladder` (F06)

What to calculate:
- How big a system fits on this roof (kWp)
- How much electricity it produces per year (kWh)
- How much of that the household actually uses vs feeds into the grid (self-consumption ratio)

How:
- Google Solar API takes the address coordinates and returns roof data — segments, area, pitch, azimuth, shading — already computed from satellite
- Best roof segments selected (south-facing, low shading)
- Panel count calculated from usable roof area (1 panel = 1.7m², 380Wp each)
- System kWp = panel count × 0.38
- Annual yield kWh = system kWp × sunshine hours × performance ratio
- Self-consumption split: 30% used by household without battery, 70% with battery (Layer 2)

```
system_kwp           → e.g. 9.5 kWp
annual_yield_kwh     → e.g. 9,230 kWh/year  (from Google Solar API irradiance)
self_consumption_pct → 30% without battery / 70% with battery

monthly_electricity_saving = annual_yield × self_consumption × grid_price / 12
monthly_feedin_revenue     = annual_yield × (1 − self_consumption) × 0.082 / 12

TOTAL electricity bucket = saving + feed-in = €X/month
```

Fallback if Google Solar unavailable: `system_kwp × 980 kWh/kWp` (PVGIS DE average).
Existing PV: credit incremental yield only — no double-count against current bill.

---

## Layer 2 — Battery (Electricity bucket — arbitrage)
**File:** `domain/savings/electricity_layer.py` → `battery_arbitrage_value()`
**Status:** ✅ implemented & wired into `build_ladder` (F07)

Builds on Layer 1's running state.

```
added_kwh        = max(0, recommended_batt_kwh − existing_battery_kwh)
total_kwh        = existing_battery_kwh + added_kwh

# (a) Extra self-consumption: autarky 0.30 → 0.60
extra_self_kwh   = (0.60 − 0.30) × annual_consumption_kwh
extra_self_value = extra_self_kwh × retail_price − extra_self_kwh × 0.0778

# (b) Dynamic-tariff arbitrage (SMARD day-ahead spread)
arbitrage_value  = total_kwh × 300 cycles × 0.90 round-trip × dynamic_spread

L2 €/mo += (extra_self_value + arbitrage_value) / 12
```

---

## Layer 3 — Heat Pump (Heating bucket)
**File:** `domain/savings/heatpump_layer.py` → `compute_heating_baseline()`
**Status:** ✅ implemented & wired into `build_ladder` (F08)

Two cases depending on existing equipment (§3.2):
- **Case A** — fossil (OIL/GAS) → new HP
- **Case B** — old/inefficient HP (age ≥ 12 yrs or SCOP < 3.0) → efficiency upgrade

```
# Heat demand from actual fuel spend (Case A) or back-calculated from old SCOP (Case B)
new_SCOP          = 3.5 (Case A) / 4.0 (Case B)
hp_electricity    = heat_demand_kwh / new_SCOP
annual_consumption_kwh += hp_electricity          # ← lifts L1/L2 self-consumption value

solar_covered     = hp_electricity × overlap      # 0.15 PV-only · 0.30 +battery
hp_grid_cost      = (hp_electricity − solar_covered) × retail_price / 12

L3 €/mo = baseline_heating_cost − hp_grid_cost
```

Case B KfW note: HP→HP replacement has no Klima-Geschwindigkeitsbonus → 30% grant, not 50%.

---

## Layer 4 — EV Charger (Mobility bucket)
**File:** `domain/savings/ev_layer.py` → `baseline_mobility_cost_year()` / `new_mobility_cost_year()`
**Status:** ✅ implemented & wired into `build_ladder` (F09)

Two cases:
- **Case A** — petrol/diesel → EV (fuel cost → cheap home charging)
- **Case B** — existing EV, no home charger → wallbox (public charging → home charging)

```
ev_kwh_year       = km_year × 18 kWh / 100 km
annual_consumption_kwh += ev_kwh_year             # ← flexible load, big self-cons. uplift
home_charge_cost  = ev_kwh_year × 0.20 / 12      # blend: PV surplus + off-peak + occasional public

# Baseline displaced:
# Case A: current fuel spend (km_year × consumption × fuel_price)
# Case B: public charging spend (ev_kwh_year × 0.45)

L4 €/mo = baseline_mobility_cost / 12 − home_charge_cost
```

Street-only parking (no wallbox possible) → Layer 4 not offered.

---

## Layer 5 — Subsidy catalog + Crawler
**File:** `domain/savings/subsidy_layer/catalog.py` (request-time) · `crawler.py` (background refresh)
**Status:** ✅ catalog wired into the engine — `resolve_subsidies()` builds a `SubsidyContext`
that `engine.recommend()` injects so the KfW heat-pump rate is data-driven
(`heat_pump_a` = 30% base + 20% speed bonus = 50%; `heat_pump_b` = 30%). 🔶 `crawler.refresh_federal()`
(weekly Tavily+LLM refresh) is the stretch demo moment.

Request-time path: `RecommendationService` calls `resolve_subsidies()` (reads `subsidy_catalog`,
offline-safe seed fallback) → `SubsidyContext` → `engine.recommend(..., subsidies=ctx)`. The engine
reads `combined_rate(component)`; it never imports a KfW constant when a context is injected.

```
Cron: every 7 days
  → scrape KfW 458 Merkblatt       (kfw.de)
  → scrape BAFA EV grant page      (bafa.de)
  → scrape Bundesnetzagentur EEG   (bundesnetzagentur.de)
  → scrape Länder grants           (optional)
  → LLM parses each page → extracts { rate, cap_eur, valid_from, source_url }
  → upserts rows in subsidy_catalog WHERE valid_until IS NULL
  → stamps fetched_at = now()
```

Supabase `subsidy_catalog` table:
```
programme        — 'kfw_458_base' | 'kfw_458_speed_bonus' | 'vat_pv_battery' | ...
component        — 'heat_pump_a' | 'pv' | 'battery' | 'ev_charger'
rate             — 0.30 (fraction) or flat EUR
cap_eur          — max grant in EUR (null = no cap)
source_url       — official page crawled (required)
fetched_at       — last crawler run
valid_from       — date subsidy became active
valid_until      — null = still in force
```

Demo moment: "last refreshed X days ago" chip in UI + manual refresh button that re-runs crawler live, updates table, recalculates saving on screen.

Fallback: if crawler fails, last known values in Supabase are used — request never blocked.
