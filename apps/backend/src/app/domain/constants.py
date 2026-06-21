"""Pure physics and policy constants used by the savings engine.

Monetary prices do not belong here. They are injected through PricingContext.
"""

from __future__ import annotations

AUTARKY_PV_ONLY: float = 0.30
AUTARKY_WITH_BATTERY: float = 0.60
BATTERY_CYCLES_PER_YEAR: int = 300
BATTERY_ROUND_TRIP_EFFICIENCY: float = 0.90

PETROL_CONSUMPTION_L_PER_100KM: float = 7.0
DIESEL_CONSUMPTION_L_PER_100KM: float = 6.0
EV_CONSUMPTION_KWH_PER_100KM: float = 18.0

DEFAULT_OLD_HEATPUMP_SCOP: float = 2.8

# Heat pump SCOP constants (§3.2)
NEW_HEATPUMP_SCOP_FOSSIL: float = 3.5  # Case A: fossil fuel → new HP
NEW_HEATPUMP_SCOP_OLDHP: float = 4.0  # Case B: old HP → modern HP

# KfW subsidy rates (§6)
KFW_FOSSIL: float = 0.50  # 50% for fossil → HP replacement
KFW_OLDHP: float = 0.30  # 30% for old HP → new HP upgrade

# PV specific yield fallback (PVGIS default, kWh/kWp/yr)
SPECIFIC_YIELD_FALLBACK: float = 980.0

# Oil boiler constants (§3.2)
OIL_KWH_PER_LITRE: float = 10.0
OIL_BOILER_EFFICIENCY: float = 0.85
GAS_BOILER_EFFICIENCY: float = 0.90

# HP offer threshold: age (years) above which old HP is considered for Case B
HP_OFFER_AGE_THRESHOLD_YEARS: int = 12

# Long-term horizon for the three-tier dashboard framing (high tier "invest in
# the future"): cumulative net saving is projected over this many years.
LIFETIME_HORIZON_YEARS: int = 20

# Battery sizing clamp (kWh)
BATTERY_MIN_KWH: float = 5.0
BATTERY_MAX_KWH: float = 10.0