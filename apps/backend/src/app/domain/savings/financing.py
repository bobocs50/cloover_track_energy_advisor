"""Financing (annuity loan) + subsidy application.

Owner: Lukas (engine)
Feature ID: F11 (financing + confidence)
"""

from __future__ import annotations


def annuity(principal: float, annual_rate: float, term_months: int) -> float:
    """Monthly annuity installment for an amortising loan (spec §6).

    At zero APR the installment is a flat linear repayment.
    A zero principal produces a zero installment.
    """
    if principal == 0.0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate == 0.0:
        return principal / term_months
    growth = (1.0 + monthly_rate) ** term_months
    return principal * monthly_rate * growth / (growth - 1.0)