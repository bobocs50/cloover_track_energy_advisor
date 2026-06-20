# §9 elaborated — Dashboard Data Specification (customer report)

> **Companion to** [`system_workflow.md` §9](./system_workflow.md). This file expands the dashboard
> sketch into a **data spec for UI/UX**: it answers two questions exactly —
> **(1) what data do we *show the customer* to hit our goal**, and **(2) what data does the
> *calculation* need**. Written from a marketing & sales lead's seat, so every customer-facing
> element is tagged with the conversion job it does.
> **v0.1 · 2026-06-20**

---

## 0. The goal, stated as a sales target (so the data has a job)

The dashboard is not a calculator — it is the **conversion surface**. Its single job is:

> **Get the homeowner to click *“Apply for Cloover financing”* on the deepest *profitable* rung, with
> enough belief in the number that they don't bounce to “let me think about it.”**

Deepest profitable rung = the full bundle wherever the optimiser says so = **highest contract value**
for Cloover *and* highest lifetime saving for the customer — the interests are aligned, which is the
honest core of the pitch. Every datum we show must do one of five jobs (the funnel we organise around):

| Tag | Funnel job | The question in the customer's head it answers |
|---|---|---|
| **A — Attention** | Hook with the headline value | *“Is there a real number in this for me?”* |
| **I — Interest** | Build the value, layer by layer | *“Where does the saving actually come from?”* |
| **D — Desire** | Make them *want* it (money + identity) | *“What does my life look like after this?”* |
| **T — Trust** | Make the number believable | *“Why should I believe this isn't a sales fantasy?”* |
| **U — Urgency** | Make *now* better than *later* | *“Why not wait a year?”* |
| **X — aCtion** | Remove friction to the click | *“What exactly happens if I say yes?”* |

The two lists below are the deliverable. **List 1** = customer-facing (serves the funnel). **List 2** =
calculation-only (serves the engine). The overlap is deliberate and small: a few engine outputs (capex,
saving, subsidy) graduate into List 1; most engine *inputs/constants* stay hidden behind the
assumptions drawer.

---

## 1. LIST 1 — Data shown to the customer (organised by dashboard zone)

Nine zones, top to bottom. Each is a card/section in the live configurator **and** a section in the
static proposal PDF (the two share one data model — §4). Every row carries its funnel tag and whether it
is **always** shown or **conditional**.

### Zone 1 — Hero: the headline saving `[A]`

The first screen. One number dominates; everything else here exists to frame it.

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| **Monthly saving (current selection)** | `YOUR SAVING: €X / month` — biggest text on the page | A | ✅ | `monthly_saving_eur` (North Star) |
| **After-payoff saving** | `→ €Y / month once the loan is paid off` | A/D | ✅ | `saving_after_payoff` |
| **Before → after spend** | `Today €435/mo  →  with the bundle €Z/mo` (bar or arrow) | A | ✅ | baseline spend, `new_energy_cost + installment` |
| **Confidence band** | `± €35` chip beside the headline | T | ✅ | aggregated band (§7 drivers) |
| **Annual + lifetime saving** | toggle: `€X/mo · €X·12/yr · €XX,XXX over 15 yrs` | D | ✅ | derived from monthly × horizon |
| **Break-even** | `Pays for itself in year N` | T/D | ✅ | `break_even_month` |

> **Sales note.** Lead with the *monthly* number (digestible, fits a household budget conversation), but
> always offer the **lifetime** toggle — the €30k–€60k cumulative figure is what closes. Never show the
> headline without the **± band** right next to it: an unqualified number reads as a sales lie, a banded
> one reads as engineering.

### Zone 2 — The configurator ladder (the value, built click by click) `[I]`

The Check24-style spine. This is where belief is manufactured: the customer *builds* the number
themselves, so they own it.

| Per-layer data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| Layer identity + size | `☀️ Solar 9 kWp`, `🔋 Battery 8 kWh`, `♨️ Heat pump`, `🚗 EV charger` | I | ✅ | sizing (§5) |
| **This layer's marginal €/mo** | `−€24/mo` … `+€124/mo` — the honest contribution of *this* tick | I | ✅ | `Δ_net(layer)` (§6.1) |
| Capex + after-subsidy capex | `€22k − €11k KfW 458 = €11k` (strike the gross, show the net) | I/D | ✅ | `Δ_capex`, subsidy (§6.5) |
| Toggle state | on / off / **owned ✓** | I | ✅ | `selection`, existing-equipment flags |
| **“Already installed ✓ — no capex”** | grey badge on owned items | T | conditional | §3.2 existing-equipment |
| Per-layer micro-explainer | `“still on oil? this layer”` · `“cheap home charging vs public”` | I | ✅ | layer case (A/B) |
| **Up-sell diff line** | `“PV+battery (−€24) → full bundle +€120 — the HP & EV displace the oil & petrol you still burn”` | I/U | conditional | optimiser diff (§6.4) |
| Running total | `TOTAL +€120/mo now → €364/mo after payoff  ± €35` | A/I | ✅ | `cumulative_net` |

> **Sales note.** The **negative/zero early rungs are a feature, not a bug** — solar alone is `−€24`,
> battery is `≈ €0`. Showing them honestly is the single biggest trust play in the whole product: it
> proves the tool isn't just inflating numbers to sell hardware, which makes the big *positive* full-
> bundle number credible. The up-sell line is the highest-leverage sentence on the page — it reframes a
> bigger loan as a *bigger saving*, which is the literal Cloover thesis (§6.2).

### Zone 3 — The upside curve & break-even timeline (the honest story) `[T][D]`

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| Honest savings curve | small chart: `≈ cost-neutral early → climbs → €364/mo after payoff` | T/D | ✅ | monthly net over loan term |
| Break-even marker | vertical line at year N on the curve | T | ✅ | `break_even_month` |
| Cost of doing nothing | `Doing nothing = €XX,XXX of energy bills over 15 yrs (energy prices rising ~X%/yr)` | U/D | ✅ | baseline × inflation projection |

> **Sales note.** “Cost of inaction” is the most under-used datum in energy sales. The customer's true
> alternative is **not €0** — it's a rising bill. Showing the do-nothing line *next to* the bundle line
> turns a “spend money” decision into a “which bill do you want” decision. This is new vs the §9 sketch
> and worth building.

### Zone 4 — Financing summary (the anchor) `[X][T]`

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| Total capex | `€XX,XXX hardware + install` | T | ✅ | Σ `Δ_capex` |
| **Total subsidy secured** | `− €11,000 KfW 458 · 0% VAT on PV & battery` (as a *win*, itemised) | D/T | ✅ | §6.5 |
| Monthly installment | `€X/mo over 180 months` | X | ✅ | `installment` |
| APR / term / downpayment | small print, editable | T | ✅ | financing params (Cloover product) |
| **Net monthly position** | `installment €244  −  saving €364  =  +€120 in your pocket` | A/X | ✅ | North Star restated |
| What's free with the bundle | `Smart meter · dynamic tariff · Cloover energy manager — included` | D/X | ✅ | bundle definition |

> **Sales note.** Present the subsidy as **money we already won for you**, itemised (KfW €11k, VAT 0%) —
> not as an abstract “after subsidy.” And always restate financing as the **net position** (saving minus
> installment), because the installment in isolation triggers loss-aversion; the net figure reframes it
> as income.

### Zone 5 — Certainty & assumptions (trust engine) `[T]`

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| Confidence chip + **biggest driver** | `± €35 — biggest factor: self-consumption ratio` | T | ✅ | §7 |
| Four certainty drivers | irradiance · dynamic tariff · subsidies · self-consumption, each with its band | T | expandable | §7 table |
| **Official-source badges** | `Solar yield: EU PVGIS · Prices: Bundesnetzagentur · Subsidy: KfW` | T | ✅ | §11 sources |
| Assumptions drawer | editable list (occupants, roof tilt, SCOP, spread…) → **live re-run, band tightens** | T | expandable | intake + §10 defaults |

> **Sales note.** The **editable assumptions drawer that re-runs live** is a trust weapon: letting the
> skeptic *change an input and watch the band shrink* converts “I don't believe your assumptions” into
> “these are now *my* assumptions.” Name the **biggest driver** explicitly — vague confidence reads as
> hedging; a named driver reads as expertise.

### Zone 6 — Feasibility, permits & social proof (risk removal) `[T][U]`

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| Permits panel | all green ✓ (`no building permit needed — verfahrensfrei`) | T | ✅ | Site-Check (§4) |
| The one real flag | `🟡 Listed building — needs heritage sign-off` *only if present* | T | conditional | Denkmal check |
| Parking / wallbox feasibility | `🟢 Driveway — home charging possible` | T | conditional | OSM + checkbox |
| **Neighbour social proof** | `40+ homes in 10119 already switched` | T/U | conditional | MaStR seed (§4) |
| GEG obligation note | `New heating must be ≥65% renewable — your oil boiler is on the clock` | U | conditional | GEG timeline (§4) |

> **Sales note.** “No permit needed” removes the #1 silent objection in German home-energy (*Bürokratie*).
> Social proof (`40+ neighbours`) is the cheapest conversion lift we have — surface it whenever the PLZ
> seed exists; fall back to silence (never a fake number) where it doesn't.

### Zone 7 — Beyond money: identity, comfort, independence (desire) `[D]`

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| **CO₂ avoided** | `− X tonnes CO₂ / year ≈ Y flights Berlin–NYC` | D | ✅ | demand × emission factors |
| **Energy independence** | `You'll be ~80% self-sufficient in electricity` | D | ✅ | autarky factor on final state |
| Comfort wins | `Heat pump cools in summer · no more oil deliveries · charge at home overnight` | D | ✅ | static per selected layers |
| Home-value uplift | `Better Energieausweis rating → higher resale value` | D | optional | static qualitative |

> **Sales note.** Money opens the door; **identity and comfort close it**. Autarky % (“independent from
> the grid / from Putin's gas”) is the single most emotionally resonant non-financial metric in the 2026
> German market — give it headline treatment, not a footnote. Translate CO₂ into a tangible equivalent
> (flights / trees / car-km); raw tonnes don't land.

### Zone 8 — Why now (urgency) `[U]`

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| GEG deadline | `Municipal heat-planning deadline: 30 Jun 2026 (your city)` | U | conditional | §4 timeline + city size |
| **Subsidy-secured-now** | `KfW 458 covers €11k today — rules tighten over time` | U | ✅ | §6.5 |
| Feed-in tariff decay | `EEG feed-in is 7.78 ct now and steps down — lock today's terms` | U | ✅ | §10 EEG note |
| Energy-price trend | `Grid electricity has risen ~X%/yr` | U | ✅ | Destatis trend |

> **Sales note.** Urgency in this product is *real and citable*, not manufactured — GEG deadlines,
> declining feed-in, a subsidy regime that only gets stingier. Cite the source on each so it reads as a
> warning from an advisor, not a pushy salesman.

### Zone 9 — The personal close & CTA `[X]`

| Data point | What the customer sees | Tag | Always? | Comes from |
|---|---|---|---|---|
| **Claude narrative** | 3 sentences, plain German: why *this* config fits *this* home | D/T | ✅ | Advisor LLM (asserts to payload) |
| Primary CTA | green **`Apply for Cloover financing`** | X | ✅ | — |
| Secondary CTA | `Download proposal (PDF)` · `Email me this` | X | ✅ | proposal export |
| What happens next | `1 Apply · 2 Free site visit · 3 Install — no commitment to see your offer` | X | ✅ | static |

> **Sales note.** End every report with a **risk-free micro-commitment** (“see your offer — no
> commitment”), not the full “buy now.” The Claude paragraph is the human handshake; it must assert
> every figure against the payload (§15 risk) so it can never contradict the numbers above it.

---

## 2. LIST 2 — Data the *calculation* needs (engine, mostly hidden)

These feed the four-layer engine (§5–§6). Most never appear on screen; the **“Shown?”** column marks the
few that graduate into List 1 (capex, saving, subsidy) or surface inside the assumptions drawer.

### 2.1 Customer inputs (intake — §3)

| Data | Why the calc needs it | Shown? |
|---|---|---|
| Address {street, house_no, city, PLZ} | → lat/lon (irradiance), grid fee, permits, roof geometry | echoed only |
| `floor_area_m2` | heat-load (L3), roof-size sanity | drawer |
| `building_year` | heat-load factor (L3) | drawer |
| `occupants` | base load / consumption scaling | drawer |
| Electricity spend €/mo | electricity baseline (L1/L2) | Zone 1 (before) |
| Heating {fuel, €/mo} | heating baseline + L3 upside | Zone 1 (before) |
| Mobility {kind, km_month \| €/mo} | L4 energy need (km canonical, §3.3) | drawer |
| Existing: `pv_kwp`, `battery_kwh`, `heatpump_year`, `ev`, `ev_charger` | which layers are offered + capex-on-delta only (§3.2) | “owned ✓” badge |

### 2.2 Resolver / enrichment (per-PLZ + roof — §10, §14.2)

| Data | Why | Shown? |
|---|---|---|
| lat/lon | PVGIS irradiance | no |
| `specific_yield` (PLZ) | L1 yield fallback | no |
| `retail_price` (Destatis + per-PLZ grid fee) | every displaced-import € (L1–L4) | drawer |
| `climate_zone`, `mastr_count` | heat-load nuance; social proof | Zone 6 (count) |
| Roof geometry {usable_roof_m2, tilt, azimuth} | L1 sizing + PVGIS params | drawer |
| Site-Check flags {roof_ok, parking, heritage, GEG} | layer gating + Zone 6 | Zone 6 |

### 2.3 Prices — injected from `price_catalog` (§12)

`pv_per_kwp`, `battery_per_kwh`, `heatpump_fixed`, `wallbox_fixed`, `oil/gas/petrol/diesel`,
`retail_per_kwh`, `feedin_per_kwh`, `public_charge_per_kwh`. → drive every capex and €/kWh.
**Shown?** only as aggregated capex/subsidy (Zone 2/4); never the raw unit prices.

### 2.4 Physics & policy constants (§10)

autarky factors (0.30 / ~0.60) · SCOP new 4.0 / old 2.8 · PV→HP overlap (0.15 / 0.30) · heat-load by
Baujahr · 1800 full-load hrs · consumption L/100km (7.0 / 6.0) · EV 18 kWh/100km · home-blended €0.20 ·
dynamic spread €0.12 · battery 300 cycles × 0.90 round-trip · KfW % · 0% VAT · EEG 7.78 ct.
**Shown?** the *driver-level* ones surface in the assumptions drawer (SCOP, autarky, spread); the rest stay internal.

### 2.5 Engine intermediates (computed, mostly internal)

| Intermediate | Role | Shown? |
|---|---|---|
| `annual_consumption_kwh` (base + HP + EV, accumulating) | the keystone — lifts self-consumption across layers (§6.2) | autarky % only |
| `annual_yield_kwh`, `self_consumed_kwh`, `exported_kwh` | L1/L2 value split | no |
| `heat_demand_kwh`, `hp_electricity_kwh` (SCOP), `solar_covered_kwh` | L3 | no |
| `ev_kwh_year` | L4 | no |
| `Δ_gross`, `Δ_capex`, `Δ_installment`, **`Δ_net`** per layer | the ladder marginals | **Zone 2 (`Δ_net`, capex)** |
| `cumulative_net`, `break_even_month`, `saving_after_payoff` | headline + curve | **Zones 1/3** |
| confidence band per driver | certainty | **Zone 5 (aggregate)** |

> **Design rule that falls out of this split:** the engine returns **everything**; the dashboard **shows
> ~15% of it by default** and tucks the driver-level rest behind the assumptions drawer. The 85% that
> stays hidden is exactly what would make a homeowner's eyes glaze — but it must be *one click away*, or
> the skeptic has nothing to inspect and the trust play (Zone 5) collapses.

---

## 3. The structure for UI/UX — zones, priority, and progressive disclosure

A single ranked spine for the designer. **Tier 1 = above the fold / always visible. Tier 2 = scroll /
expand. Tier 3 = drawer / PDF appendix.**

```
TIER 1 (the 5-second pitch)         TIER 2 (the build & belief)        TIER 3 (the proof)
┌─────────────────────────────┐     ┌──────────────────────────┐      ┌─────────────────────┐
│ Z1 Hero saving + band       │     │ Z3 Honest curve / break- │      │ Z5 Assumptions      │
│    before→after, lifetime   │     │    even / cost-of-nothing│      │    drawer (editable)│
│ Z2 Ladder (4 toggles, Δ€,   │     │ Z4 Financing anchor      │      │    source badges    │
│    capex, up-sell line)     │     │ Z6 Permits + social proof│      │ Z7 CO₂ / autarky    │
│ Z9 CTA (sticky)             │     │ Z8 Why-now urgency       │      │    detail           │
└─────────────────────────────┘     │ Z9 Claude paragraph      │      │ PDF: full appendix  │
                                     └──────────────────────────┘      └─────────────────────┘
```

**Two surfaces, one data model.** The *live configurator* is interactive (toggles → re-run) and leads
with Tier 1. The *proposal PDF / report* is the same data, linearised and signed off — Tier 1 becomes
the cover page, Tiers 2–3 become the body, and the assumptions/sources become the appendix (audit
trail). Build the data contract once (§14.1 `Recommendation`) and render it twice.

**Progressive-disclosure law:** never show a calc constant before its result. The customer meets `+€124/mo`
first; only if they open the drawer do they meet `EV 18 kWh/100km` behind it. List 2 lives *under* List 1.

---

## 4. The marketing lead's five non-negotiables (what makes this convert)

1. **Honesty is the conversion strategy, not a compliance checkbox.** The `−€24` solar rung and the
   `≈€0` battery rung are the proof-of-integrity that makes the `+€120` full-bundle believable. Cutting
   them to “look better” would *lower* conversion. Keep them.
2. **Always pair the headline with the band and the source.** `€120/mo ± €35, from EU PVGIS + KfW data`
   converts; a bare `€120/mo` reads as a pop-up ad.
3. **Reframe every cost as a net position.** Subsidy = “money we won for you.” Installment = shown only
   beside the saving it's smaller than. Loan = “a bigger saving,” via the up-sell line.
4. **Sell the second product: identity.** Autarky % and CO₂-as-flights do work the euro number can't —
   they're why a customer chooses the *full* bundle over the cheapest profitable rung.
5. **Make urgency real and cited.** GEG deadline, declining feed-in, tightening KfW — all true, all
   sourced. Manufactured scarcity would poison the trust the rest of the page builds.

> **Net:** List 1 is the funnel (A→I→D→T→U→X). List 2 is the evidence locker behind it. The dashboard
> wins when the customer *builds the number themselves* (Z2), *can't poke a hole in it* (Z5/Z6), *wants
> the life behind it* (Z7), and *has a risk-free next step* (Z9).
