# Subsidy Layer (F26)

Automatic federal subsidy catalog. Reads from Supabase, falls back offline.
The engine reads this layer's output — it never imports a subsidy constant directly.

---

## What this layer does

1. **Stores** the 6 federal MVP subsidy rows in Supabase (`subsidy_catalog`)
2. **Crawls** official pages weekly (Tavily → OpenAI → gate → upsert) to keep rates fresh
3. **Resolves** which rows apply to a household and computes the grant per product
4. **Feeds** the financing engine (F11) via `SubsidyContext` — same pattern as `price_catalog → PricingContext`

The North Star number is: `monthly_saving = gross_saving − installment`.
This layer reduces `installment` by reducing `capex_after_subsidy = capex − grant`.

---

## The 6 federal rows

| Programme | Component | Rate | Cap | Source |
|---|---|---|---|---|
| `kfw_458_base` | `heat_pump_a` | 30% | €21k | KfW 458 |
| `kfw_458_base` | `heat_pump_b` | 30% | €21k | KfW 458 |
| `kfw_458_speed_bonus` | `heat_pump_a` | 20% | €21k | KfW 458 |
| `vat_pv_battery` | `pv` | 0% | — | §12(3) UStG |
| `vat_pv_battery` | `battery` | 0% | — | §12(3) UStG |
| `bafa_ev_umweltbonus` | `ev_charger` | 0% | €0 | BAFA (ended 17 Dec 2023) |

**Component keys:**
- `heat_pump_a` — replacing a fossil boiler (GAS/OIL → HP). Gets base 30% + speed bonus 20% = **50%**.
- `heat_pump_b` — replacing an old heat pump. Gets base 30% **only** — no speed bonus (§5.3/R4).
- `pv`, `battery` — 0% VAT already baked into `price_catalog` prices. Shown as cited row, not a cash grant.
- `ev_charger` — BAFA ended Dec 2023. `valid_until = 2023-12-17` gates it out automatically.

**KfW 70% hard cap** applies only to `heat_pump_a` / `heat_pump_b`. PV/battery/EV have their own programme limits via `cap_eur`.

---

## Key numbers (Nahholz demo, typical GAS boiler household)

```
heat_pump_a capex:   €22,000
  kfw_458_base:       30% → −€6,600
  kfw_458_speed_bonus:20% → −€4,400
  combined grant:         −€11,000   ← biggest single subsidy
  after subsidy:       €11,000

pv capex:            €15,000  (0% VAT already in price)
battery capex:        €5,600  (0% VAT already in price)
ev_charger capex:     €1,200  (no grant)

total bundle:        €43,800
total grant:        −€11,000
after subsidies:     €32,800
installment (15yr):    ~€251/mo
```

The €11k heat-pump grant is what makes the "day-one saving" story work.

---

## Data flow

```
CRAWL (weekly / POST /advisor/subsidies/refresh)
  Tavily search → raw page text
  OpenAI gpt-4o-mini → structured JSON rows
  _validate_gate → passes? → subsidy_catalog (live, engine reads)
                   fails?  → subsidy_catalog_staging (quarantine)

ENGINE (per user request)
  resolve_subsidies(request_date, supabase_url, supabase_key)
    → reads subsidy_catalog WHERE valid_from ≤ today AND valid_until ≥ today (or null)
    → falls back to offline seed if Supabase unavailable
    → returns SubsidyContext grouped by component

  components_for_intake(household) → list of component keys
  ctx.compute_grant(component, capex) → grant_eur
  capex_after_subsidy = capex − grant_eur
  → passed to F11 financing engine as SubsidyContext
```

---

## Files

```
subsidy_layer/
├── catalog.py    — Subsidy + SubsidyContext dataclasses, resolve_subsidies(), components_for_intake()
├── crawler.py    — SOURCES, Tavily fetch, OpenAI extract, _validate_gate, refresh_federal()
└── __init__.py   — public exports

tests/unit/domain/
├── test_subsidy_catalog.py  — 17 unit tests, zero network (offline fallback)
└── test_subsidy_crawler.py  — 13 gate tests, no-op tests, zero network

supabase/migrations/
└── 202606210001_f26_subsidy_catalog.sql  — subsidy_catalog + subsidy_catalog_staging + 6-row seed

apps/backend/src/app/api/routes/
└── subsidies.py  — GET /api/v1/advisor/subsidies, POST /api/v1/advisor/subsidies/refresh
```

---

## API endpoints

**`GET /api/v1/advisor/subsidies`**
Returns all currently-eligible rows + example grants for a typical bundle. Works offline (fallback seed). No auth required.

**`POST /api/v1/advisor/subsidies/refresh`**
Runs the Tavily+OpenAI crawler live. Takes ~10–15s. Returns `{promoted, quarantined, errors, crawled_at}`.
Demo chip: "Subsidies verified X hours ago [Refresh now]".

---

## Gate logic (`_validate_gate`)

Before any crawled row is promoted to `subsidy_catalog`:

| Check | Rule | On fail |
|---|---|---|
| Rate bounds | `0 ≤ rate ≤ 1` | Quarantine |
| Source URL | must start with `https://` | Quarantine |
| Rate jump | `\|proposed − live\| ≤ 0.25` (if live row exists) | Quarantine |

Quarantined rows go to `subsidy_catalog_staging` with a `diff_note`. The engine keeps the last-good live value. A bad scrape cannot corrupt the North Star number.

---

## Offline / demo safety (R9)

- `resolve_subsidies(supabase_url='', supabase_key='')` uses the in-memory fallback seed — identical to the migration rows.
- All unit tests run with no network and no Supabase.
- For the demo: seed the DB once with the migration, backdate `valid_from` to look like it crawled last week, click "Refresh now" live to prove the mechanism works.

---

## How the financing engine (F11) consumes this

```python
ctx = resolve_subsidies(request_date=date.today(), supabase_url=..., supabase_key=...)
components = components_for_intake(
    replaces_fossil_heating=(household.heating.fuel in ('GAS', 'OIL')),
    has_existing_heatpump=(household.existing_heatpump_year is not None),
    wants_pv=True,
    wants_battery=True,
    wants_ev_charger=True,
)
for component in components:
    grant = ctx.compute_grant(component, capex_by_product[component])
    capex_after_subsidy = capex_by_product[component] - grant
    # pass capex_after_subsidy to annuity calculation
    assumptions += ctx.applied_assumptions(component)  # cited in response
```

`SubsidyContext` is injected alongside `PricingContext` — the engine never imports `0.30` or `0.50` directly (AC6).

---

## Invariants

- **Engine never imports a subsidy constant** — all rates come from `SubsidyContext`.
- **Date gating is data, not logic** — `valid_until` drops expired rows automatically. No code change needed when a programme ends.
- **Crawl failures don't corrupt the number** — failed/suspicious rows quarantine in `staging`.
- **Offline demo works** — fallback seed is in-memory, identical to the DB rows.
- **Every subsidy is cited** — each `Assumption` in the response carries `source_url` (R7).
- **KfW 70% cap is component-scoped** — applies only to `heat_pump_a` / `heat_pump_b`, not PV/EV.
