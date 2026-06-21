/**
 * FROZEN CONTRACT — F02 (Heimwende Energy Advisor)
 *
 * Hand-authored TypeScript types matching specs/api/openapi.yaml exactly.
 * Once tooling is available, regenerate with:
 *
 *   make gen-client
 *   (pnpm --dir apps/frontend dlx openapi-typescript ../../specs/api/openapi.yaml
 *           -o src/lib/api-types.ts)
 *
 * Do NOT edit without a reviewed PR that bumps the openapi.yaml in the same commit.
 *
 * Per-layer "+€/mo" in the configurator:
 *   layer_delta(n) = alternatives[n].monthly_saving_eur - alternatives[n-1].monthly_saving_eur
 * alternatives[] values are CUMULATIVE — no extra API call needed (AC5).
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

/** Fossil heating fuel.  District heating is out of scope for v1 (§3.2). */
export type FuelType = "OIL" | "GAS";

/** Mobility type.  EV = already drives electric; NONE = no car. */
export type CarType = "PETROL" | "DIESEL" | "EV" | "NONE";

/** Traffic-light status for a single feasibility check (🟢/🟡/ℹ️). */
export type FeasibilityStatus = "green" | "amber" | "info";

// ---------------------------------------------------------------------------
// Request sub-types
// ---------------------------------------------------------------------------

/** Full postal address — mandatory for Site-Check roof geometry and permit lookups. */
export interface Address {
  /** Street name. */
  street: string;
  /** House/building number. */
  house_no: string;
  /** City. */
  city: string;
}

/** Current heating system details. */
export interface HeatingInput {
  fuel: FuelType;
  /** Average monthly heating spend in EUR. */
  eur_month: number;
}

/**
 * Current mobility profile.
 * km_month is the canonical quantity; eur_month is accepted as an alternative
 * and converted to km by the engine (§3.3).  At least one should be provided.
 */
export interface MobilityInput {
  kind: CarType;
  /** Average monthly distance driven in km (canonical). */
  km_month?: number;
  /** Average monthly spend on fuel/charging in EUR (alternative to km_month). */
  eur_month?: number;
}

/**
 * À-la-carte product selection (optional stretch, §6.3).
 * If omitted from Household, the engine runs the full nested ladder.
 */
export interface SelectionInput {
  pv?: boolean;
  battery?: boolean;
  heat_pump?: boolean;
  ev?: boolean;
}

// ---------------------------------------------------------------------------
// Request root
// ---------------------------------------------------------------------------

/**
 * Customer intake profile — the primary API seam (F02).
 *
 * address + plz + floor_area_m2 + building_year + occupants +
 * electricity_eur_month + heating + mobility are ALL required.
 */
export interface Household {
  /** Full postal address (mandatory). */
  address: Address;
  /**
   * 5-digit German postcode.  Drives irradiance, grid fees, climate zone,
   * and prices independently of address (§3.1).
   */
  plz: string;
  /** Living floor area in m².  Required for heat-load calculation (L3). */
  floor_area_m2: number;
  /** Year of construction.  Drives heat-load factor (§10 table) for L3. */
  building_year: number;
  /** Number of occupants.  Drives load profile and consumption scaling. */
  occupants: number;
  /** Average monthly electricity spend in EUR before any upgrades. */
  electricity_eur_month: number;
  /** Current heating system details. */
  heating: HeatingInput;
  /** Current mobility profile. */
  mobility: MobilityInput;
  /**
   * Installed PV capacity in kWp.  Default 0 (no existing PV).
   * If > 0, the ladder credits only the incremental yield above this.
   */
  existing_pv_kwp?: number;
  /**
   * Installed battery capacity in kWh.  Default 0 (no existing battery).
   * If > 0, the ladder adds only the delta up to the recommended size.
   */
  existing_battery_kwh?: number;
  /**
   * Year the existing heat pump was installed, or null if no HP present.
   * null → fossil/no-HP case (Layer 3 = Case A fossil → new HP).
   * If set: age ≥ 12 yrs or est. SCOP < 3.0 → Layer 3 = Case B efficiency upgrade;
   * modern HP → Layer 3 Δ = 0 (not offered).
   */
  existing_heatpump_year?: number | null;
  /**
   * Optional rated thermal output of the existing heat pump in kW.
   * Overrides the area-method estimate for the Case-B baseline.
   */
  existing_heatpump_power_kw?: number | null;
  /**
   * Optional measured or nameplate SCOP of the existing heat pump.
   * Overrides the age-regression fallback for the Case-B baseline.
   */
  existing_heatpump_scop?: number | null;
  /**
   * True if the household already drives an EV.  Changes mobility baseline
   * from fuel cost to public charging cost (§3.2).
   */
  existing_ev?: boolean;
  /**
   * True if the household already has a home wallbox.
   * EV=true + charger=false → Layer 4 = Case B wallbox-only offer.
   * EV=true + charger=true → Layer 4 Δ = 0 (not offered).
   */
  existing_ev_charger?: boolean;
  /**
   * À-la-carte selection (optional).  If omitted, the engine runs the full
   * nested ladder and picks the best rung (recommended mode).
   */
  selection?: SelectionInput;
}

// ---------------------------------------------------------------------------
// Response sub-types
// ---------------------------------------------------------------------------

/** Monthly spend breakdown by energy bucket for a given scenario. */
export interface Breakdown {
  /** Projected monthly electricity spend under this scenario. */
  electricity_eur_month: number;
  /** Projected monthly heating spend under this scenario. */
  heating_eur_month: number;
  /** Projected monthly mobility spend under this scenario. */
  mobility_eur_month: number;
}

/** Capital expenditure breakdown for a scenario (F20 capex column). */
export interface Capex {
  /** Total gross capital cost before subsidies in EUR. */
  gross_eur: number;
  /** Total subsidy / grant applied in EUR. */
  subsidy_eur: number;
  /** Net capex after subsidy deduction in EUR (= gross − subsidy). */
  after_subsidy_eur: number;
  /** Human-readable explanation of the subsidies applied. */
  subsidy_note: string;
}

/** Uncertainty band on monthly_saving_eur (F11/F21/F23 ±band display). */
export interface Confidence {
  /** Half-width of the confidence band in EUR/mo. */
  band_eur: number;
  /** Lower bound of monthly saving in EUR/mo. */
  low_eur: number;
  /** Upper bound of monthly saving in EUR/mo. */
  high_eur: number;
  /** Name of the biggest uncertainty source (shown in the UI confidence chip). */
  biggest_driver: string;
}

/** Incremental up-sell from one scenario to the next rung up the ladder (§6.4). */
export interface Upsell {
  /** The current (lower) scenario being compared from. */
  from_scenario_id: string;
  /** The recommended (higher) scenario being up-sold to. */
  to_scenario_id: string;
  /** Incremental monthly saving of upgrading (to − from).  May be large when multiple layers are skipped. */
  delta_eur_month: number;
  /** Markdown copy explaining why the upgrade is worthwhile. */
  reason_md: string;
}

/**
 * A labelled assumption used in the calculation (F23 assumptions drawer).
 * editable:true rows are shown and re-run the engine when changed.
 */
export interface Assumption {
  /** Field name / assumption key. */
  field: string;
  /** Human-readable value string. */
  value: string;
  /** Official source or derivation note. */
  source: string;
  /** If true, the user can override this value to tighten the confidence band. */
  editable: boolean;
}

/**
 * One rung of the cumulative savings ladder.
 *
 * monthly_saving_eur is the CUMULATIVE net saving at this rung (installment deducted).
 * Per-layer Δ = alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur.
 */
export interface ScenarioResult {
  /** Stable identifier for this scenario (used by upsell references). */
  scenario_id: string;
  /** Human-readable scenario name displayed in the configurator. */
  label: string;
  /** Projected monthly spend breakdown. */
  breakdown: Breakdown;
  /** Capital expenditure breakdown. */
  capex: Capex;
  /** Monthly loan installment in EUR (annuity on after_subsidy capex). */
  installment_eur_month: number;
  /**
   * Net monthly saving vs baseline = gross_saving − installment_eur_month.
   * CUMULATIVE across all layers up to this rung.  May be negative early rungs.
   */
  monthly_saving_eur: number;
  /** Monthly saving once the loan is fully paid off (= gross saving only). */
  saving_after_payoff_eur: number;
  /** Month number at which cumulative_net first turns non-negative. */
  break_even_month: number;
  /** Uncertainty band on monthly_saving_eur. */
  confidence: Confidence;
  /** Plain-language payback summary for the honest-curve display. */
  payback_note: string;
}

/**
 * One of three packaged offers (low / middle / high) shown side-by-side on the
 * dashboard, derived from the cumulative ladder.
 *
 * - low    — cost-efficient entry: cheapest, lowest capital at risk.
 * - middle — best-value milestone: strongest saving below the full commitment.
 * - high   — future-proof: the full bundle, headlined by the cumulative saving
 *            over lifetime_years plus the permanent €/mo after payoff.
 *
 * scenario_id references a ScenarioResult in alternatives[]; the numeric fields
 * are copied here so a dashboard card is self-contained. Every € figure is
 * grounded in the ladder — never the LLM prose.
 */
export interface Tier {
  /** Tier rank. */
  id: "low" | "middle" | "high";
  /** Marketing name for the tier card. */
  name: string;
  /** One-line pitch shown under the tier name. */
  tagline: string;
  /** ID of the ScenarioResult (in alternatives[]) this tier maps to. */
  scenario_id: string;
  /** Human-readable bundle label. */
  label: string;
  /** Total capital after subsidies for this tier. */
  capex_after_subsidy_eur: number;
  /** Monthly loan installment for this tier. */
  installment_eur_month: number;
  /** Net monthly saving today (installment deducted). May be small/negative for low tier. */
  monthly_saving_eur: number;
  /** Permanent monthly saving once the loan is paid off. */
  saving_after_payoff_eur: number;
  /** Month at which cumulative cash flow turns positive. */
  break_even_month: number;
  /** Horizon used for the long-term cumulative figure. */
  lifetime_years: number;
  /**
   * Cumulative NET saving over lifetime_years: net saving during the loan plus
   * after-payoff saving for the remaining years. The high-tier headline.
   */
  lifetime_saving_eur: number;
  /** The single big number to feature on this tier's card. */
  headline_eur: number;
  /** Short caption explaining what headline_eur represents. */
  headline_caption: string;
  /** Markdown one-liner on why a household would pick this tier. */
  rationale_md: string;
}

// ---------------------------------------------------------------------------
// Response root
// ---------------------------------------------------------------------------

/**
 * Full advisor output.
 *
 * best is the recommended scenario (highest monthly_saving_eur).
 * alternatives[] is the FOUR-RUNG cumulative ladder in order ☀️→🔋→♨️→🚗.
 *
 * Per-layer "+€X/mo" displayed by the configurator:
 *   layer_delta(n) = alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur
 * No extra API call needed (AC5 identity).
 *
 * explanation_md and proposal_copy_md are LLM prose (F16) — never the numeric authority;
 * every € in them must also appear in a ScenarioResult.
 */
export interface Recommendation {
  /** The recommended (highest-saving) scenario. */
  best: ScenarioResult;
  /** The four cumulative ladder rungs in order (☀️→🔋→♨️→🚗). */
  alternatives: ScenarioResult[];
  /**
   * Three packaged offers (low / middle / high) derived from the ladder, shown
   * side-by-side on the dashboard. Always ordered low → middle → high.
   */
  tiers: Tier[];
  /** Incremental up-sell from the second-best to the best rung. */
  upsell: Upsell;
  /**
   * Baseline monthly spend before any upgrades (electricity + heating + mobility).
   * Drives the before/after display (F21).
   */
  current_monthly_spend_eur: number;
  /**
   * LLM-generated Markdown paragraph explaining why this config fits this home (F16).
   * Plain German for the demo.  NEVER the numeric source of truth.
   */
  explanation_md: string;
  /**
   * LLM-generated Markdown proposal copy for the CTA panel (F16).
   * NEVER the numeric source of truth.
   */
  proposal_copy_md: string;
  /** Labelled assumptions used in the calculation (F23 drawer). */
  assumptions: Assumption[];
}

// ---------------------------------------------------------------------------
// Site-Check
// ---------------------------------------------------------------------------

/** Subset of Household used for the site-check call (§14.2). */
export interface SiteCheckRequest {
  address: Address;
  plz: string;
  floor_area_m2: number;
  building_year: number;
}

/**
 * One permit / obligation check result (§4).
 * product names the product category, check names the specific rule,
 * status is the traffic light, message is human-readable.
 */
export interface FeasibilityFlag {
  /** Product category (e.g. "Solar PV", "Heat pump", "EV charger", "Battery"). */
  product: string;
  /** Name of the specific rule or check performed. */
  check: string;
  /** Traffic-light result. */
  status: FeasibilityStatus;
  /** Human-readable result message. */
  message: string;
}

/** Location-resolved energy parameters returned by the site-check (F15). */
export interface EnergyContext {
  /** Latitude resolved from the address. */
  lat: number;
  /** Longitude resolved from the address. */
  lon: number;
  /** Annual PV yield per kWp for this location (kWh/kWp/yr). */
  specific_yield_kwh_per_kwp: number;
  /** Local retail electricity price in EUR/kWh. */
  retail_price_eur_kwh: number;
  /** Local grid fee in EUR/kWh (per-PLZ overlay from Netztransparenz). */
  grid_fee_eur_kwh: number;
  /** DE climate zone identifier (used for heat-load table, §5.3). */
  climate_zone: string;
  /**
   * Number of installed PV systems in this PLZ from MaStR (social proof).
   * null if unknown (no MaStR data for this PLZ).
   */
  mastr_neighbour_count: number | null;
}

/** Permit and feasibility result for the site-check pre-step. */
export interface SiteCheckResponse {
  /**
   * True if the roof is viable for PV (no Denkmalschutz block, no structural flag).
   * Amber = viable with caveats (user should confirm heritage listing).
   */
  roof_ok: boolean;
  /** Per-product permit and obligation flags (§4 table). */
  feasibility_flags: FeasibilityFlag[];
  /** Location-resolved energy parameters. */
  energy_context: EnergyContext;
  /** Labelled assumptions used in the site-check (editable → re-run). */
  assumptions: Assumption[];
}
