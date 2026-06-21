# Check Depth Plan

## Goal

The live activity feed and final offer should explain more than "a check happened."
Each backend layer should expose the concrete checks it ran, the data source behind
each check, the reasoning result, and how that result affects the offer.

The user should understand:

- What was checked.
- Which source backed the check.
- Why the check matters.
- Whether it passed, warned, failed, or changed the economic reasoning.
- How it feeds into the final offer.

## Permit Checks

The permit check should be grouped by category. Under each category, the UI should
show specific checks, not one generic "permit check" item.

Required categories:

| Category | Specific checks to expose |
|---|---|
| Location | PLZ to Bundesland, municipality, local planning context |
| Solar permissions | LBO baseline, Denkmalschutz, Bebauungsplan, neighbour precedent, MaStR evidence |
| Heat pump permissions | Denkmalschutz, outdoor-unit restrictions, GEG boiler-age context, TA Laerm/noise risk |
| EV charger permissions | Private parking, WEG/apartment risk, legal approval path |
| Battery permissions | Installation advisory, MaStR registration advisory |

Every row should include a Supabase-backed source path where possible:

- Source name.
- Source URL or source table.
- Fetched timestamp.
- Whether the result came from live internet, Supabase cache, seeded fallback, or static rule.

The activity feed should be fast. Permit checks should run concurrently and stream
worker results as soon as they finish. The UI should not wait for all checks before
showing the first result.

## Permit Check Reasoning

Each check should carry an explanation field that is usable in the offer later.

Example:

```text
Heat pump: existing heat pump is old.
Reasoning: because the household already has an old heat pump, the offer should
consider replacement economics instead of fossil-to-heat-pump conversion economics.
Subsidy effect: old heat pump replacement can still qualify for a subsidy path,
but it uses a different eligibility/rate than oil or gas replacement.
Offer effect: show replacement saving, new SCOP improvement, capex, subsidy,
and lifetime value.
```

The important point: the check result is not only a traffic light. It should become
structured reasoning that the final offer page can reuse.

## Google Solar Checks

Google Solar should not be presented as only "angle and side." It is doing much
more and the UI/docs should show that depth.

Specific checks to expose:

| Category | Specific checks to expose |
|---|---|
| Address resolution | Geocode address to lat/lng, fallback if geocoding fails |
| Building match | Closest building insight, confidence/fallback source |
| Roof geometry | Roof segments, segment area, usable area, south-facing area |
| Orientation | Dominant orientation, azimuth bucket, roof-side selection |
| Panel capacity | Panel footprint, maximum panel count, estimated kWp |
| Yield | Site-specific kWh/kWp/year, fallback yield when Google coverage is missing |
| Visual evidence | Screenshot/map/roof-image evidence if available, or explicit note that data came from Google Solar API rather than visual screenshot |
| Offer impact | PV size, self-consumption, export, battery usefulness, monthly saving impact |

Each Google Solar result should include:

- Source: Google Geocoding, Google Solar, Supabase cache, or fallback.
- Raw measurement summary.
- Human-readable reasoning.
- Downstream field updated, such as `specific_yield`, `usable_area_m2`, `max_modules`, or `orientation`.

## Supabase Source Requirement

There should always be a Supabase story in the backend path:

- Price catalog is read from Supabase.
- Subsidy catalog is read from Supabase.
- Permit support data and cached evidence should be read from Supabase when available.
- Completed recommendation/proposal should be written back to Supabase.

For live internet checks, Supabase should be the persistence/cache layer:

```text
internet source -> normalized check result -> Supabase cache/table -> stream event -> offer reasoning
```

This gives the platform an audit trail instead of a one-time opaque API call.

## Activity Feed UI Requirement

The current live feed is too general. It should show nested, specific checks under
each category.

Desired shape:

```text
Permit checks
  Solar
    Denkmalschutz registry: pass
    Bebauungsplan RAG: warn
    MaStR neighbour precedent: pass
  Heat pump
    GEG boiler-age rule: pass
    TA Laerm/noise density: warn
  EV charger
    Private parking: pass
    WEG risk: info

Google Solar
  Building matched: pass
  South-facing usable roof area: 42 m2
  Max modules: 21
  Site yield: 982 kWh/kWp/year
  Offer impact: solar rung adds EUR X/month
```

Each check should appear quickly as its worker completes.

## Offer Page Requirement

The final offer should reuse the reasoning from the activity feed.

Examples:

- If the household has an old heat pump, explain replacement economics and subsidy
  eligibility instead of generic heat-pump conversion.
- If Google Solar found strong south-facing roof area, explain why PV sizing is high.
- If permit checks warn on Denkmal or Bebauungsplan, show that the offer is still
  possible but requires confirmation.
- If Supabase subsidy data changes the capex, show the subsidy value and source.

The offer should not just show the result. It should show why this recommendation
is correct for this specific household.

## Evaluation Agent

An LLM-based EvaluationAgent should be introduced, but it must not compute money
or overwrite deterministic engine results.

Core rule:

```text
Engine computes.
EvaluationAgent evaluates and explains.
Number guard verifies.
Offer and 3D UI display.
```

The EvaluationAgent should receive structured facts from the deterministic layers:

- Household input.
- Existing equipment.
- Google Solar facts.
- Permit checks.
- Supabase pricing context.
- Supabase subsidy context.
- Low/mid/high tier outputs.
- Monthly savings, capex, payback, and lifetime value from the engine.

It should return structured reasoning:

- Recommended tier.
- Why this tier is recommended.
- Product-level reasons.
- Replacement vs keep-existing recommendation.
- Permit or source risks.
- Installer verification steps.
- Customer-facing explanation text.
- Visual/action hints for the 3D model.

The agent may decide that one computed path is better than another, but only by
comparing computed facts. It must not invent new financial figures.

## Evaluation Timing

Use two phases.

### Phase 1: live 3D / activity reasoning

After enough facts exist, emit compact reasoning cards into the live feed and 3D
view. This should not block the fast checks.

Good first implementation:

1. Run all deterministic checks and savings tiers.
2. Start `evaluation_started`.
3. Call EvaluationAgent once with the complete payload.
4. Stream 3-5 reasoning cards into the activity feed.
5. Use the same structured output to update the 3D proposal state.

Later implementation:

- Add smaller mid-pipeline evaluation calls after Google Solar.
- Add smaller mid-pipeline evaluation calls after permit checks.
- Keep these optional so the UI remains fast when the LLM is slow.

### Phase 2: final offer reasoning

At the end, the EvaluationAgent should produce final offer reasoning:

- Best tier.
- Why low/mid/high differ.
- Why replacement is or is not recommended.
- Which checks create risk.
- Which sources support the recommendation.
- What the installer should verify next.

## Replacement Reasoning

Replacement reasoning is required, especially for old equipment.

Example:

```text
Current state: old heat pump.
Option A: keep existing heat pump.
Option B: replace with modern heat pump.

Engine computes:
- old SCOP
- new SCOP
- electricity delta
- replacement capex
- subsidy value
- monthly saving delta
- payback/lifetime value

EvaluationAgent decides:
- replace / keep / verify
- why
- what to show in the 3D model
- what to show in the final offer
```

The same pattern should apply to other products:

- Old fossil heating -> replace with heat pump.
- Old heat pump -> replace with efficient heat pump if computed payback supports it.
- No PV -> add PV if Google Solar yield and roof area support it.
- Battery -> add only if self-consumption/lifetime value supports it.
- EV charger -> add only if mobility/private-parking assumptions support it.

## 3D Proposal State

The 3D model should become a visual proposal preview, not decoration.

The EvaluationAgent/deterministic planner should output a shared action plan,
for example `HouseActionPlan` or `VisualRecommendationState`.

Example shape:

```json
{
  "recommended_tier": "mid",
  "actions": [
    {
      "product": "solar",
      "action": "add",
      "reason": "Google Solar found usable south-facing roof area.",
      "visual": "show_solar_panels"
    },
    {
      "product": "heat_pump",
      "action": "replace",
      "reason": "Existing heat pump is old; replacement improves SCOP and qualifies for subsidy logic.",
      "visual": "highlight_heat_pump_replacement"
    },
    {
      "product": "battery",
      "action": "add",
      "reason": "Battery increases self-consumption.",
      "visual": "show_battery"
    }
  ]
}
```

The 3D model should consume this state:

| Action | 3D behavior |
|---|---|
| `add solar` | Show panels on roof. |
| `add battery` | Show battery near building wall. |
| `replace heat pump` | Show old unit muted/outlined and new unit highlighted. |
| `remove heat pump` | Hide or fade existing unit if replacement/removal is recommended. |
| `add EV charger` | Show wallbox/charger. |
| permit warning | Show yellow marker on affected component. |
| permit fail/blocker | Show red/blocked marker on affected component. |

Permit checks should not directly decide the full product plan. They provide
feasibility, risk, and evidence. The engine and EvaluationAgent combine permit
facts with savings, subsidies, current equipment, and solar potential to produce
the final action plan.

## 3D Interaction Requirement

Keep interaction simple.

Clickable 3D components are useful if they explain the offer:

```text
Click solar panels -> roof/yield/savings reason.
Click heat pump -> replacement/subsidy/efficiency reason.
Click battery -> self-consumption reason.
Click EV charger -> mobility/private-parking reason.
```

Do not build a heavy modal. Use a compact side panel, tooltip, or drawer.

Priority:

1. Tier cards control visible 3D components.
2. Clicking a visible component shows one compact reason panel.
3. Warning markers show permit/subsidy risks.
4. Rich screenshot/image evidence can come later.

## Tier Dashboard Requirement

The low/mid/high tier controls should not be only buttons. They should be compact
dashboard cards that explain what changes.

Each tier card should include:

- Tier name.
- Monthly saving.
- Included components.
- One-line reason.
- Risk/status chip.

Example:

```text
Low
Solar starter
EUR X/month
Adds: solar panels
Best if: lowest commitment.

Mid
Balanced home upgrade
EUR Y/month
Adds: solar + battery + heat pump replacement
Best if: best practical payback.

High
Full electrification
EUR Z/month
Adds: solar + battery + heat pump + EV charger
Best if: maximum long-term savings.
```

When a tier is selected:

- The 3D model changes.
- The active tier card changes.
- The reason panel changes.
- Component labels/reasons change.

The purpose is to make the 3D model a decision interface. Without tier-driven
visual changes and reasoning, the 3D model is mostly decorative.

## Implementation Notes

- Extend backend `PipelineEvent.payload` with check-level reasoning fields.
- Keep `PermitCheck` structured and reusable by both activity feed and offer page.
- Consider a shared `EvidenceSource` shape: `name`, `url`, `table`, `fetched_at`,
  `source_type`, `confidence`.
- Add Supabase-backed caching/persistence for live check evidence.
- Group frontend activity feed by category and product layer.
- Feed selected reasoning snippets into the final `Recommendation`/offer payload.
- Add EvaluationAgent output schema with recommended tier, reasons, risks,
  replacement decisions, and visual action plan.
- Add `HouseActionPlan`/`VisualRecommendationState` to the backend contract only
  after the deterministic tier outputs are stable.
- Keep the LLM behind a number guard. It may choose wording and explain tradeoffs,
  but it may not generate new savings/cost values.
