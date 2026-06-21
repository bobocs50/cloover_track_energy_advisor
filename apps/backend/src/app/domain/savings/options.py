"""Configurator marginals — per-component delta summaries (F10).

Owner: Lukas (engine)
Feature ID: F10 (optimiser / configurator)

The ladder in scenarios.py returns cumulative ScenarioResult rungs.
Marginals are the consecutive differences; the FE derives them from
alternatives[n].monthly_saving_eur − alternatives[n-1].monthly_saving_eur
(AC5 identity).  This module exposes a helper for internal use.
"""

from __future__ import annotations

from app.domain.models import ScenarioResult


def marginals(alternatives: list[ScenarioResult]) -> list[float]:
    """Return per-layer delta_net_eur_month from the cumulative ladder.

    Σ marginals == alternatives[-1].monthly_saving_eur exactly (no
    rounding of intermediates).
    """
    if not alternatives:
        return []
    result = []
    prev = 0.0
    for rung in alternatives:
        result.append(rung.monthly_saving_eur - prev)
        prev = rung.monthly_saving_eur
    return result