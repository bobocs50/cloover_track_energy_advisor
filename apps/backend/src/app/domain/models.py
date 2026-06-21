"""Domain models — FROZEN CONTRACT (F02).

These Pydantic v2 models are the BE source of truth, hand-authored to match
specs/api/openapi.yaml exactly.  Once tooling is available, regenerate with:

    make gen-models
    (datamodel-codegen --input specs/api/openapi.yaml --input-file-type openapi
                       --output apps/api/src/app/domain/models.py)

Owner: Zhou (backend) / Lukas (engine)
Feature ID: F02 (contract) — F17 wires endpoints — F03/F05-F11 implement engine.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FuelType(StrEnum):
    """Fossil heating fuel.  District heating is out of scope for v1 (§3.2)."""

    OIL = "OIL"
    GAS = "GAS"


class CarType(StrEnum):
    """Mobility type.  EV = already drives electric; NONE = no car."""

    PETROL = "PETROL"
    DIESEL = "DIESEL"
    EV = "EV"
    NONE = "NONE"


class FeasibilityStatus(StrEnum):
    """Traffic-light status for a single feasibility check (green/amber/info)."""

    GREEN = "green"
    AMBER = "amber"
    INFO = "info"


# ---------------------------------------------------------------------------
# Request sub-objects
# ---------------------------------------------------------------------------


class Address(BaseModel):
    """Full postal address — mandatory for Site-Check roof geometry and permit lookups."""

    street: str = Field(..., description="Street name (Straße).", examples=["Unter den Linden"])
    house_no: str = Field(..., description="House/building number (Hausnummer).", examples=["17"])
    city: str = Field(..., description="City (Ort/Stadt).", examples=["Berlin"])


class HeatingInput(BaseModel):
    """Current heating system details."""

    fuel: FuelType = Field(..., description="Fossil fuel type.")
    eur_month: float = Field(
        ..., description="Average monthly heating spend in EUR.", examples=[180]
    )


class MobilityInput(BaseModel):
    """Current mobility profile.

    km_month is the canonical quantity; eur_month is accepted as an alternative
    and converted to km by the engine (§3.3).  At least one should be provided.
    """

    kind: CarType = Field(..., description="Vehicle type.")
    km_month: float | None = Field(
        default=None,
        description="Average monthly distance driven in km (canonical).",
        examples=[1200],
    )
    eur_month: float | None = Field(
        default=None,
        description="Average monthly spend on fuel/charging in EUR (alternative to km_month).",
        examples=[160],
    )


class SelectionInput(BaseModel):
    """À-la-carte product selection (optional stretch, §6.3).

    If omitted from Household, the engine runs the full nested ladder and
    recommends the best rung.
    """

    pv: bool = Field(default=False)
    battery: bool = Field(default=False)
    heat_pump: bool = Field(default=False)
    ev: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Request root
# ---------------------------------------------------------------------------


class Household(BaseModel):
    """Customer intake profile — the primary API seam (F02).

    address + plz + floor_area_m2 + building_year + occupants +
    electricity_eur_month + heating + mobility are ALL required.
    """

    address: Address = Field(..., description="Full postal address (mandatory).")
    plz: str = Field(
        ...,
        description=(
            "5-digit German postcode.  Drives irradiance, grid fees, climate zone, "
            "and prices independently of address (§3.1, labelled assumption)."
        ),
        examples=["10115"],
    )
    floor_area_m2: int = Field(
        ...,
        description="Living floor area in m².  Required for heat-load calculation (L3).",
        examples=[140],
    )
    building_year: int = Field(
        ...,
        description="Year of construction.  Drives heat-load factor (§10 table) for L3.",
        examples=[1985],
    )
    occupants: int = Field(
        ...,
        description="Number of occupants.  Drives load profile and consumption scaling.",
        examples=[3],
    )
    electricity_eur_month: float = Field(
        ...,
        description="Average monthly electricity spend in EUR before any upgrades.",
        examples=[95],
    )
    heating: HeatingInput = Field(..., description="Current heating system details.")
    mobility: MobilityInput = Field(..., description="Current mobility profile.")
    locale: Literal["de", "en"] = Field(
        default="en",
        description=(
            "Language for generated prose (UI chrome is localised client-side). Default English."
        ),
    )

    # Existing-equipment fields (§3.2)
    existing_pv_kwp: float = Field(
        default=0,
        description=(
            "Installed PV capacity in kWp.  0 = no existing PV.  "
            "If > 0, the ladder credits only the incremental yield above this."
        ),
        examples=[0],
    )
    existing_battery_kwh: float = Field(
        default=0,
        description=(
            "Installed battery capacity in kWh.  0 = no existing battery.  "
            "If > 0, the ladder adds only the delta up to the recommended size."
        ),
        examples=[0],
    )
    existing_heatpump_year: int | None = Field(
        default=None,
        description=(
            "Year the existing heat pump was installed, or null if no HP present.  "
            "null → fossil/no-HP case (Layer 3 = Case A fossil → new HP).  "
            "If set: age ≥ 12 yrs or est. SCOP < 3.0 → Layer 3 = Case B efficiency upgrade; "
            "modern HP → Layer 3 Δ = 0 (not offered)."
        ),
        examples=[None],
    )
    existing_heatpump_power_kw: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Rated thermal output of the existing heat pump in kW. "
            "Overrides the area-method estimate when supplied."
        ),
        examples=[8.0],
    )
    existing_heatpump_scop: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Measured or nameplate SCOP of the existing heat pump. "
            "Overrides the age-regression fallback when supplied."
        ),
        examples=[2.5],
    )
    existing_ev: bool = Field(
        default=False,
        description=(
            "True if the household already drives an EV.  Changes mobility baseline "
            "from fuel cost to public charging cost (§3.2)."
        ),
        examples=[False],
    )
    existing_ev_charger: bool = Field(
        default=False,
        description=(
            "True if the household already has a home wallbox.  "
            "EV=True + charger=False → Layer 4 = Case B wallbox-only offer.  "
            "EV=True + charger=True → Layer 4 Δ = 0 (not offered)."
        ),
        examples=[False],
    )
    selection: SelectionInput | None = Field(
        default=None,
        description=(
            "À-la-carte selection (optional).  If omitted, the engine runs the full "
            "nested ladder and picks the best rung (recommended mode)."
        ),
    )


# ---------------------------------------------------------------------------
# Response sub-objects
# ---------------------------------------------------------------------------


class Breakdown(BaseModel):
    """Per-bucket monthly SAVING contribution for a scenario (gross, before installment).

    The three buckets sum to the scenario's gross monthly saving (= saving_after_payoff_eur).
    These are savings vs today's spend, NOT the post-upgrade spend (system_workflow §9, §14.1).
    """

    electricity_eur_month: float = Field(
        ...,
        description=(
            "Monthly electricity saving vs today (solar self-consumption + battery arbitrage)."
        ),
        examples=[61],
    )
    heating_eur_month: float = Field(
        ...,
        description=(
            "Monthly heating saving vs today (heat pump displacing oil/gas); "
            "0 if no heat-pump rung."
        ),
        examples=[55],
    )
    mobility_eur_month: float = Field(
        ...,
        description=(
            "Monthly mobility saving vs today (EV home charging displacing petrol); "
            "0 if no EV rung."
        ),
        examples=[26],
    )


class Capex(BaseModel):
    """Capital expenditure breakdown for a scenario (F20 capex column)."""

    gross_eur: float = Field(
        ...,
        description="Total gross capital cost before subsidies in EUR.",
        examples=[42000],
    )
    subsidy_eur: float = Field(
        ...,
        description="Total subsidy / grant applied in EUR.",
        examples=[11000],
    )
    after_subsidy_eur: float = Field(
        ...,
        description="Net capex after subsidy deduction in EUR (= gross − subsidy).",
        examples=[31000],
    )
    subsidy_note: str = Field(
        ...,
        description="Human-readable explanation of the subsidies applied.",
        examples=["€22k HP − 50% KfW 458 = €11k; PV/battery 0% VAT"],
    )


class Confidence(BaseModel):
    """Uncertainty band on monthly_saving_eur (F11/F21/F23 ±band display)."""

    band_eur: float = Field(
        ...,
        description="Half-width of the confidence band in EUR/mo.",
        examples=[35],
    )
    low_eur: float = Field(
        ...,
        description="Lower bound of monthly saving in EUR/mo.",
        examples=[85],
    )
    high_eur: float = Field(
        ...,
        description="Upper bound of monthly saving in EUR/mo.",
        examples=[155],
    )
    biggest_driver: str = Field(
        ...,
        description="Name of the biggest uncertainty source.",
        examples=["self-consumption ratio (autarky 0.60 ± 0.10)"],
    )


class Upsell(BaseModel):
    """Incremental up-sell from one scenario to the next rung up the ladder (§6.4)."""

    from_scenario_id: str = Field(
        ...,
        description="The current (lower) scenario being compared from.",
        examples=["pv-battery"],
    )
    to_scenario_id: str = Field(
        ...,
        description="The recommended (higher) scenario being up-sold to.",
        examples=["full-bundle"],
    )
    delta_eur_month: float = Field(
        ...,
        description="Incremental monthly saving of upgrading (to − from).",
        examples=[144],
    )
    reason_md: str = Field(
        ...,
        description="Markdown copy explaining why the upgrade is worthwhile.",
        examples=[
            (
                "Going from PV+battery (−€24/mo) to the full bundle lands **+€120/mo** "
                "because you're still burning oil + petrol that the heat pump and EV displace."
            )
        ],
    )


class Assumption(BaseModel):
    """A labelled assumption used in the calculation (F23 assumptions drawer)."""

    field: str = Field(
        ...,
        description="Field name / assumption key.",
        examples=["specific_yield_kwh_per_kwp"],
    )
    value: str = Field(
        ...,
        description="Human-readable value string.",
        examples=["980 kWh/kWp"],
    )
    source: str = Field(
        ...,
        description="Official source or derivation note.",
        examples=["PVGIS fallback (PLZ 10115)"],
    )
    editable: bool = Field(
        ...,
        description=("If True, the user can override this value to tighten the confidence band."),
        examples=[True],
    )


class ScenarioResult(BaseModel):
    """One rung of the cumulative savings ladder.

    monthly_saving_eur is the CUMULATIVE net saving at this rung (installment deducted).
    Per-layer Δ = alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur.
    """

    scenario_id: str = Field(
        ...,
        description="Stable identifier for this scenario (used by upsell references).",
        examples=["full-bundle"],
    )
    label: str = Field(
        ...,
        description="Human-readable scenario name displayed in the configurator.",
        examples=["☀️ Solar + 🔋 Battery + ♨️ Heat pump + 🚗 EV charger"],
    )
    breakdown: Breakdown = Field(..., description="Projected monthly spend breakdown.")
    capex: Capex = Field(..., description="Capital expenditure breakdown.")
    installment_eur_month: float = Field(
        ...,
        description="Monthly loan installment in EUR (annuity on after_subsidy capex).",
        examples=[244],
    )
    monthly_saving_eur: float = Field(
        ...,
        description=(
            "Net monthly saving vs baseline = gross_saving − installment_eur_month.  "
            "CUMULATIVE across all layers up to this rung.  May be negative early rungs."
        ),
        examples=[120],
    )
    saving_after_payoff_eur: float = Field(
        ...,
        description="Monthly saving once the loan is fully paid off (= gross saving only).",
        examples=[364],
    )
    break_even_month: int = Field(
        ...,
        description="Month number at which cumulative_net first turns non-negative.",
        examples=[156],
    )
    confidence: Confidence = Field(..., description="Uncertainty band on monthly_saving_eur.")
    payback_note: str = Field(
        ...,
        description="Plain-language payback summary for the honest-curve display.",
        examples=["€120/mo from day one; EV is the biggest single contributor"],
    )


# ---------------------------------------------------------------------------
# Three packaged tiers (dashboard offer cards)
# ---------------------------------------------------------------------------


class Tier(BaseModel):
    """One of three packaged offers shown side-by-side on the dashboard.

    The three tiers are derived from the cumulative ladder (alternatives[]) and
    are designed to be shown together (not chosen between by the engine):

    - ``low``    — cost-efficient entry: the cheapest rung with the fastest
                   payback (lowest capital at risk).
    - ``middle`` — best-value milestone: the strongest net monthly saving below
                   the full commitment.
    - ``high``   — future-proof: the full bundle.  Its headline is the long-term
                   story — cumulative saving over ``lifetime_years`` plus the
                   permanent €/mo once the loan is paid off.

    ``scenario_id`` references the matching ScenarioResult in alternatives[];
    the numeric fields are copied here so a dashboard card is self-contained.
    Every € figure here is also derivable from a ScenarioResult (numeric
    authority is never the LLM prose).
    """

    id: Literal["low", "middle", "high"] = Field(
        ..., description="Tier rank.", examples=["high"]
    )
    name: str = Field(
        ...,
        description="Marketing name for the tier card.",
        examples=["Future-Proof"],
    )
    tagline: str = Field(
        ...,
        description="One-line pitch shown under the tier name.",
        examples=["Invest in the future — maximum lifetime saving."],
    )
    scenario_id: str = Field(
        ...,
        description="ID of the ScenarioResult (in alternatives[]) this tier maps to.",
        examples=["full-bundle"],
    )
    label: str = Field(
        ...,
        description="Human-readable bundle label.",
        examples=["☀️ Solar + 🔋 Battery + ♨️ Heat pump + 🚗 EV charger"],
    )
    capex_after_subsidy_eur: float = Field(
        ..., description="Total capital after subsidies for this tier.", examples=[28200]
    )
    installment_eur_month: float = Field(
        ..., description="Monthly loan installment for this tier.", examples=[244]
    )
    monthly_saving_eur: float = Field(
        ...,
        description="Net monthly saving today (installment deducted). May be small/negative for low tier.",
        examples=[137],
    )
    saving_after_payoff_eur: float = Field(
        ...,
        description="Permanent monthly saving once the loan is paid off.",
        examples=[392],
    )
    break_even_month: int = Field(
        ..., description="Month at which cumulative cash flow turns positive.", examples=[118]
    )
    lifetime_years: int = Field(
        ..., description="Horizon used for the long-term cumulative figure.", examples=[20]
    )
    lifetime_saving_eur: float = Field(
        ...,
        description=(
            "Cumulative NET saving over lifetime_years: net saving during the loan "
            "plus after-payoff saving for the remaining years.  The high-tier headline."
        ),
        examples=[64000],
    )
    headline_eur: float = Field(
        ...,
        description="The single big number to feature on this tier's card.",
        examples=[64000],
    )
    headline_caption: str = Field(
        ...,
        description="Short caption explaining what headline_eur represents.",
        examples=["über 20 Jahre · danach €392/Monat dauerhaft"],
    )
    rationale_md: str = Field(
        ...,
        description="Markdown one-liner on why a household would pick this tier.",
        examples=["Das volle Paket: höchste Gesamtersparnis und maximale Unabhängigkeit."],
    )


# ---------------------------------------------------------------------------
# Response root
# ---------------------------------------------------------------------------


class Recommendation(BaseModel):
    """Full advisor output.

    best is the recommended scenario (highest monthly_saving_eur).
    alternatives[] is the FOUR-RUNG cumulative ladder in order ☀️→🔋→♨️→🚗.
    Per-layer "+€X/mo" displayed by the FE = consecutive differences of
    alternatives[].monthly_saving_eur (AC5 identity — no extra API call).

    explanation_md and proposal_copy_md are LLM prose (F16) — never the numeric
    authority; every € in them must also appear in a ScenarioResult.
    """

    best: ScenarioResult = Field(..., description="The recommended (highest-saving) scenario.")
    alternatives: list[ScenarioResult] = Field(
        ...,
        description="The four cumulative ladder rungs in order (☀️→🔋→♨️→🚗).",
        min_length=1,
    )
    tiers: list[Tier] = Field(
        ...,
        description=(
            "Three packaged offers (low / middle / high) derived from the ladder, "
            "shown side-by-side on the dashboard.  Always ordered low → middle → high."
        ),
        min_length=1,
    )
    upsell: Upsell = Field(
        ...,
        description="Incremental up-sell from the second-best to the best rung.",
    )
    current_monthly_spend_eur: float = Field(
        ...,
        description=(
            "Baseline monthly spend before any upgrades (electricity + heating + mobility).  "
            "Drives the before/after display (F21)."
        ),
        examples=[435],
    )
    explanation_md: str = Field(
        ...,
        description=(
            "LLM-generated Markdown paragraph explaining why this config fits this home (F16).  "
            "Plain German for the demo.  NEVER the numeric source of truth."
        ),
        examples=["Ihr Haus ist ideal für das volle Paket..."],
    )
    proposal_copy_md: str = Field(
        ...,
        description=(
            "LLM-generated Markdown proposal copy for the CTA panel (F16).  "
            "NEVER the numeric source of truth."
        ),
        examples=["**Ihr persönlicher Energieplan...**"],
    )
    assumptions: list[Assumption] = Field(
        ...,
        description="Labelled assumptions used in the calculation (F23 drawer).",
    )


# ---------------------------------------------------------------------------
# Site-Check request + response
# ---------------------------------------------------------------------------


class SiteCheckRequest(BaseModel):
    """Subset of Household used for the site-check call (§14.2).

    Accepts the address plus floor_area_m2 and building_year for roof sizing
    and heat-load.
    """

    address: Address = Field(..., description="Full postal address.")
    plz: str = Field(..., description="5-digit German postcode.", examples=["10115"])
    floor_area_m2: int = Field(..., description="Living area in m².", examples=[140])
    building_year: int = Field(..., description="Year of construction.", examples=[1985])


class FeasibilityFlag(BaseModel):
    """One permit / obligation check result (§4).

    product names the product category, check names the specific rule,
    status is the traffic light, message is human-readable.
    """

    product: str = Field(
        ...,
        description='Product category (e.g. "Solar PV", "Heat pump", "EV charger", "Battery").',
        examples=["Solar PV"],
    )
    check: str = Field(
        ...,
        description="Name of the specific rule or check performed.",
        examples=["Building permit (Baugenehmigung)"],
    )
    status: FeasibilityStatus = Field(
        ...,
        description="Traffic-light result.",
        examples=[FeasibilityStatus.GREEN],
    )
    message: str = Field(
        ...,
        description="Human-readable result message.",
        examples=["Roof PV is verfahrensfrei — no permit needed (LBO)"],
    )


class EnergyContext(BaseModel):
    """Location-resolved energy parameters returned by the site-check (F15)."""

    lat: float = Field(..., description="Latitude resolved from the address.", examples=[52.5163])
    lon: float = Field(..., description="Longitude resolved from the address.", examples=[13.3777])
    specific_yield_kwh_per_kwp: float = Field(
        ...,
        description="Annual PV yield per kWp for this location (kWh/kWp/yr).",
        examples=[980],
    )
    retail_price_eur_kwh: float = Field(
        ...,
        description="Local retail electricity price in EUR/kWh.",
        examples=[0.37],
    )
    grid_fee_eur_kwh: float = Field(
        ...,
        description="Local grid fee in EUR/kWh (per-PLZ overlay from Netztransparenz).",
        examples=[0.07],
    )
    climate_zone: str = Field(
        ...,
        description="DE climate zone identifier (used for heat-load table, §5.3).",
        examples=["DE-4"],
    )
    mastr_neighbour_count: int | None = Field(
        ...,
        description=(
            "Number of installed PV systems in this PLZ from MaStR (social proof).  "
            "None if unknown (no MaStR data for this PLZ)."
        ),
        examples=[47],
    )


class SiteCheckResponse(BaseModel):
    """Permit and feasibility result for the site-check pre-step."""

    roof_ok: bool = Field(
        ...,
        description=(
            "True if the roof is viable for PV (no Denkmalschutz block, no structural flag).  "
            "Amber = viable with caveats (user should confirm heritage listing)."
        ),
        examples=[True],
    )
    feasibility_flags: list[FeasibilityFlag] = Field(
        ...,
        description="Per-product permit and obligation flags (§4 table).",
    )
    energy_context: EnergyContext = Field(
        ...,
        description="Location-resolved energy parameters.",
    )
    assumptions: list[Assumption] = Field(
        ...,
        description="Labelled assumptions used in the site-check (editable → re-run).",
    )


# ---------------------------------------------------------------------------
# Domain-internal (not in the OpenAPI contract)
# ---------------------------------------------------------------------------


class PricingContext(BaseModel):
    """Resolved prices/fees/tariffs for a location.

    This is domain-internal: built by the Resolver from price_catalog (§12)
    and injected into the pure engine.  It is NOT part of the OpenAPI contract.
    Populated by F12/F17 (resolver).
    """

    plz: str
    retail_price_eur_kwh: float
    feedin_price_eur_kwh: float
    grid_fee_eur_kwh: float
    dynamic_spread_eur_kwh: float
    pv_per_kwp_eur: float
    battery_per_kwh_eur: float
    heatpump_fixed_eur: float
    wallbox_fixed_eur: float
    oil_per_litre_eur: float
    gas_per_kwh_eur: float
    petrol_per_litre_eur: float
    diesel_per_litre_eur: float
    public_charge_per_kwh_eur: float
    home_charge_price_eur_kwh: float
    financing_apr: float
    financing_term_months: int