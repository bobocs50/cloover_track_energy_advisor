"""Solar economics constants.

Ported from solar-pipeline/pipeline.py and INSTALLER_CONSTRAINTS.md.
Cost levers are safe to override; physics constants are not.
"""

from __future__ import annotations

# ── Retail price default (used when PricingContext not available) ─────────────
DEFAULT_RETAIL_PRICE_EUR_KWH: float = 37 / 100  # Germany average 2024

# ── Feed-in tariff (EEG 2023) ────────────────────────────────────────────────
FEED_IN_TARIFF_SMALL_EUR_KWH: float = 0.082  # ≤ 10 kWp
FEED_IN_TARIFF_LARGE_EUR_KWH: float = 0.071  # > 10 kWp portion

# ── Capex ────────────────────────────────────────────────────────────────────
BASE_PV_COST_PER_KWP_EUR: float = 750.0      # BOS: inverter + wiring + mounting (panel cost separate)
SERVICE_COST_EUR: float = 2_500.0             # Labor + planning (flat, when PV included)

# ── VAT (0% on residential PV+battery since Jan 2023) ────────────────────────
VAT_RATE: float = 0.0


def blended_feed_in(system_kwp: float) -> float:
    """Blended feed-in tariff for the system size.

    ≤ 10 kWp: flat FEED_IN_TARIFF_SMALL.
    > 10 kWp: first 10 kWp at small rate, remainder at large rate.
    """
    if system_kwp <= 10:
        return FEED_IN_TARIFF_SMALL_EUR_KWH
    return (
        10 * FEED_IN_TARIFF_SMALL_EUR_KWH
        + (system_kwp - 10) * FEED_IN_TARIFF_LARGE_EUR_KWH
    ) / system_kwp


def pv_capex(system_kwp: float, panel_count: int, cost_per_panel_eur: float) -> float:
    """Gross capex before subsidy: panels + BOS + service."""
    panel_cost = panel_count * cost_per_panel_eur
    bos_cost = system_kwp * BASE_PV_COST_PER_KWP_EUR
    return panel_cost + bos_cost + SERVICE_COST_EUR


def vat_subsidy(gross_capex: float) -> float:
    """VAT saving on PV installation (0% MwSt since Jan 2023 for residential)."""
    return gross_capex * VAT_RATE
