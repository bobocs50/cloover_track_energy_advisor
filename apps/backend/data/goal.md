# Product Goal — User Journey

The full flow from address input to dashboard. Each step fires in sequence, visible to the user.

---

## 🏆 The Winning Feature

**Live permit checks + live subsidy crawler.**

Every other team hardcodes KfW 30% and skips permits. We show permits resolving one by one *before* the number appears (trust), and our subsidy rates are crawled fresh from KfW/BAFA weekly (accuracy). One judge question — *"what if KfW changes the rate?"* — kills every other team. Not us.

Second winner: **the sales psychology layer** — customer profiling by income/age, best case first, real estate uplift, assumptions drawer for sceptics. Other teams build calculators. We build the thing that makes a difficult customer say yes before the meeting starts.

---

## Input

One form. No account, no upload, no installer visit needed.

**Mandatory:**
```
Address: street + house number, postcode (PLZ), city   — Mapbox autocomplete
Floor area (m²), building year, number of occupants
Electricity spend (€/month)
Heating: fuel type (OIL / GAS) + monthly spend (€)
Mobility: kind (PETROL / DIESEL / EV / NONE) + km/month or €/month
```

**Existing equipment (optional — unlocks Case B subsidy paths):**
```
existing_pv_kwp              already has solar panels (kWp)
existing_battery_kwh         already has battery (kWh)
existing_heatpump_year       install year of existing heat pump
existing_heatpump_power_kw   rated output of existing HP (kW)
existing_heatpump_scop       SCOP of existing HP
existing_ev                  already drives an EV
existing_ev_charger          already has a home wallbox
```

The moment the address is confirmed, all layers fire in parallel.

---

## Steps

- [x] **Step 1 — Address Input with mapbox


- [x] **Step 2 — Permit Layer (Layer 0 — Site-Check)**

  12 live checks across 4 products stream in one by one (SSE: `GET /api/v1/advisor/permits/stream`),
  each with a tick as it resolves. Real data sources, not hardcoded — every result is cited and timestamped:

  ```
  ✅ Solar PV         — verfahrensfrei under LBO, no permit needed
  ✅ Solar heritage   — property not listed (Denkmal WMS / OSM)
  ✅ Solar B-Plan     — no restriction found (Bebauungsplan RAG: Tavily + Claude)
  ✅ Neighbour proof  — 43 solar systems within this PLZ (MaStR)
  ✅ Heat pump heritage— not listed
  ✅ Heat pump B-Plan — outdoor unit permitted
  ✅ Heat pump GEG    — boiler ≥20y, replacement permitted (GEG §72)
  🟡 Heat pump noise  — dense plot, TA Lärm advisory (≤45 dB night)
  ✅ EV charger park  — private driveway confirmed
  ✅ EV charger WEG   — single-family, legal right (§554 BGB)
  ✅ Battery install  — indoor, always permitted
  ℹ️ Battery MaStR    — register after install (installer task)
  ```

  🟡 Yellow = warning, explained in plain language, then continues.
  🔴 Red (`fail`) = that product is `*_blocked` on the matrix and removed from all scenarios, reason shown.

  Sources: Denkmal WMS (7 Bundesländer + OSM fallback), Bebauungsplan via Tavily + Claude Haiku
  clause extraction, MaStR count (Supabase → public page → Tavily), OSM Overpass, and hardcoded
  GEG/LBO/TA-Lärm rules. Whole matrix cached in Supabase `permit_cache` (TTL 7 days) and summarised
  in plain German by Claude. Full backend detail: `apps/backend/src/app/domain/savings/permit_layer/INFO.md`.

- [x] **Step 3 — Solar Layer (Layer 1)**

  Google Solar API fires at address confirmation. Returns real satellite roof data:

  ```
  Address            → Am Nahholz 55, 74722 Buchen
  Geocoding          → lat 49.52, lng 9.32 (Google Geocoding API)
  Roof segments      → south-facing only (azimuth 90–270°): 145 m²
  Panel cap          → 72 panels (Trina 440Wp, 2.00 m² each)
  Orientation        → SE  (dominant south-facing segment)
  Local irradiance   → 1,034 kWh/kWp/yr  ← real satellite data, not a Germany average
  ```

  Pipeline tries every size from ~5 kWp to roof cap (~20 steps), scores all candidates,
  and returns three offers:

  ```
  BUDGET             → 15 panels / 6.6 kWp   · €10,225 · payback 11.2 yrs
                       annual yield 6,134 kWh · self-consumption 80%
                       saving €71/month electricity

  BALANCED           → 39 panels / 17.2 kWp  · €28,585 · payback 12.0 yrs
                       annual yield 15,947 kWh · self-consumption 34%
                       saving €126/month electricity

  MAX INDEPENDENCE   → 72 panels / 31.7 kWp + 20 kWh battery
                       €70,480 · payback 12.8 yrs
                       annual yield 29,469 kWh · self-consumption 20%
                       saving €176/month electricity
  ```

  Feed-in tariff (EEG 2023): ≤10 kWp → 0.082 €/kWh · >10 kWp blended → 0.071 €/kWh.
  Self-consumption rates from HTW Berlin physics table (not a flat 30% constant).

  **ELECTRICITY BUCKET** (Balanced offer) → **€126/month**

  See `apps/backend/src/app/domain/savings/solar_layer/INFO.md` for full backend physics.

- [ ] **Step 4 — Battery Layer (Layer 2)**

  ```
  Battery size       → 8 kWh
  Self-consumption   → 70% (battery lifts autarky 30% → 70%)
  Arbitrage          → remaining grid kWh × 34% dynamic tariff saving

  ELECTRICITY BUCKET → €80/month + arbitrage = €X/month
  ```

- [ ] **Step 5 — Heat Pump Layer (Layer 3)**

  ```
  Current heating    → €180/month (oil/gas)
  Heat demand        → calculated from floor area + building year
  Heat pump COP      → 3.5 (new unit)
  HP electricity     → partly covered by solar (15% overlap)

  HEATING BUCKET     → €107/month saved
  ```

  KfW 458 subsidy applied: 50% off capex (base 30% + Klima-Geschwindigkeitsbonus 20%).

- [ ] **Step 6 — EV Charger Layer (Layer 4)**

  ```
  Current fuel       → €160/month (petrol)
  Distance           → 14,800 km/year (back-calculated)
  EV electricity     → 2,668 kWh/year @ €0.20 home blended price

  MOBILITY BUCKET    → €133/month saved
  ```

- [ ] **Step 7 — Subsidy Crawler (Layer 5)**

  Runs every week. Scrapes KfW, BAFA, Bundesnetzagentur → LLM parses → writes fresh rates into `subsidy_catalog` in Supabase. Engine always reads from DB — never hardcoded.

  ```
  subsidy_catalog (Supabase):
    KfW 458 base:    30%  · cap €21,000  · fetched_at: 2026-06-20
    KfW speed bonus: 20%  · cap €21,000  · fetched_at: 2026-06-20
    VAT PV/battery:   0%  · no cap       · fetched_at: 2026-06-20
    BAFA EV:          €0  · ended        · fetched_at: 2026-06-20
  ```

  Dashboard chip: **"Subsidies verified X days ago"** + live refresh button for demo.

- [ ] **Step 8 — Dashboard**

  ```
  TODAY YOU PAY:
    Electricity   €95/month
    Heating       €180/month
    Fuel          €160/month
    ──────────────────────────
    TOTAL         €435/month

  WITH CLOOVER:
    Financing     €244/month
    Remaining     €71/month
    ──────────────────────────
    TOTAL         €315/month

  YOUR SAVING     €120/month   ← biggest number on the page
  ```

  - Bundle: Solar 9.5kWp · Battery 8kWh · Heat pump · EV charger
  - Roof: 62m² usable · south-facing · 43 neighbours already did it · all permits ✅
  - Investment: €42,000 gross → €26,850 after grants → €244/month financing
  - Break-even: month 47 (≈ 4 years) → **€364/month once paid off**
  - **Home value uplift: +€25,000–€45,000** (EPC class D → B)

  Three strategy cards (Check24-style):
  - **Optimal** — full bundle, €120/month from day one
  - **Fastest payback** — solar + heat pump, break-even in 28 months
  - **Long-term** — full bundle premium, €364/month after payoff

  **LLM paragraph — written for this specific house, in plain German:**
  > *"Ihr Haus auf der Musterstraße hat eine südausgerichtete Dachfläche von 62m² — damit liegt die jährliche Solarausbeute 18% über dem Berliner Durchschnitt. Ihr hoher Benzinverbrauch macht den EV-Lader zum größten Einzelsparer: allein €133/Monat. Das volle Paket bringt Sie von heute €435/Monat auf €315/Monat — inklusive Finanzierung."*
  Not generic copy. Claude reads the actual engine output and writes for this household.

  One button: **Jetzt Cloover-Finanzierung beantragen**

---

## Track Engineer Notes — How to make it credible & convincing

### What makes the number credible?

- **Real address data** — their actual roof (Google Solar API), their actual PLZ (local grid fees, irradiance)
- **Their real bills** — back-calculated to physical quantities, shown as editable assumptions
- **Live subsidy rates** — crawler keeps KfW/BAFA fresh, cited with source URL per subsidy row
- **Existing equipment** — old solar/old heat pump handled honestly:
  - Old solar → incremental capex only, 0% VAT on added kWp
  - Old heat pump (age ≥ 12 yrs or SCOP < 3.0) → efficiency upgrade, KfW 458 base 30%

### Customer profiling — who are we talking to?

| Profile | What matters | How to frame |
|---------|-------------|--------------|
| **High income, 45–60** | Real estate value, legacy | "Your home is worth €X more. Energy costs become irrelevant." |
| **Middle income, 35–50** | Monthly cashflow | "€120/month in your pocket from day one. No upfront cost." |
| **Low income / tight budget** | Risk of installment | "Even at 70% estimated yield, you're still better off." |
| **Already has old equipment** | Don't want to feel stupid | "Your existing solar already saves €X. We just complete the picture." |
| **Sceptic** | Doesn't trust salespeople | Assumptions drawer — every number sourced. Edit inputs live. |

### Best case scenario — show it first

Lead with **best case** (full bundle, optimal conditions). Let the customer pull it back.
Confidence band (`±€35`) makes the downside honest without killing the headline.

### Financing — how and why

- **Why finance?** — Installment (€244/mo) < current bills (€435/mo). Cash-flow positive from day one.
- **Subsidy timing** — KfW grant paid after installation. Cloover bridges the subsidy.
- **Feasibility check** — if installment > 35% of net income → flag, suggest smaller bundle.
- **Why fixed rate?** — Loan is fixed; savings are inflation-linked. Gap grows every year.

### Real estate value uplift

EPC class improvement (D → B) commands +5–15% on sale price in Germany.
Dashboard shows: **"Estimated home value uplift: +€25,000–€45,000"**
Closing argument for the 45–60 demographic — legacy and asset value, not monthly saving.
