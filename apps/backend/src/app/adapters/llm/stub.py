"""Deterministic stub advisor (no network) — F16.

Owner: Zhou (backend)
Feature ID: F16 (LLM advisor)

Default in dev/offline so the pipeline runs without any LLM API key.
All prose is derived deterministically from the payload numbers, so the
number-assertion guard always passes (AC4 / §15).

The stub output passes the guard because it only cites exact payload figures.
"""

from __future__ import annotations

from typing import Any

from app.adapters.llm.base import AdvisorLLM, assert_numbers_grounded


class StubAdvisor:
    """Deterministic AdvisorLLM implementation — no external calls.

    Generates prose by interpolating exact payload figures.
    Language follows ``locale``: "de" (default) → German, "en" → English.
    Satisfies the number-assertion guard (AC2 / AC4).
    """

    def explain(self, payload: dict[str, Any], locale: str = "en") -> dict[str, Any]:
        """Return deterministic copy derived from payload numbers in the requested locale.

        The copy cites only figures present in the payload, so the guard
        passes without retries (AC2 / §15 invariant).
        """
        if locale == "en":
            result = _explain_en(payload)
        else:
            result = _explain_de(payload)

        # Self-check: guard must pass on our own output
        all_text = (
            result["explanation_md"]
            + " "
            + result.get("upsell_reason_md", "")
            + " "
            + result.get("proposal_copy_md", "")
        )
        if not assert_numbers_grounded(all_text, payload):
            # This should never happen with the stub — but if it does, fall back
            # to a minimal safe copy that cites nothing extra.
            return _minimal_copy(payload, locale)

        return result


def _explain_de(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate deterministic German prose from payload figures."""
    best: dict[str, Any] = payload.get("best", {})
    monthly_saving = best.get("monthly_saving_eur", 0)
    saving_after_payoff = best.get("saving_after_payoff_eur", 0)
    installment = best.get("installment_eur_month", 0)
    capex = best.get("capex", {})
    after_subsidy = capex.get("after_subsidy_eur", 0)
    subsidy = capex.get("subsidy_eur", 0)
    current_spend = payload.get("current_monthly_spend_eur", 0)
    label = best.get("label", "das volle Paket")
    break_even = best.get("break_even_month", 0)

    # 3-sentence German rationale (explanation_md)
    explanation_md = (
        f"Mit {label} sparen Sie bereits ab dem ersten Monat €{monthly_saving:.0f}/mo "
        f"gegenüber Ihren bisherigen Energiekosten von €{current_spend:.0f}/mo. "
        f"Nach Kreditende sinken Ihre Kosten auf nur noch €{saving_after_payoff:.0f}/mo "
        f"— dauerhaft und unabhängig von steigenden Energiepreisen. "
        f"Der Break-even wird in Monat {break_even} erreicht, "
        f"danach gehört jede Einsparung Ihnen."
    )

    # Up-sell nudge (upsell_reason_md)
    upsell: dict[str, Any] = payload.get("upsell", {})
    delta = upsell.get("delta_eur_month", 0)
    upsell_reason_md = (
        f"Der letzte Ausbauschritt spart weitere **€{delta:.0f}/mo** "
        f"— ein entscheidender Schritt zur vollen Energieautonomie."
    )

    # Installer proposal copy (proposal_copy_md) — concise, letter-shaped.
    proposal_copy_md = (
        f"Mit {label} sparen Sie **€{monthly_saving:.0f}/mo ab Tag eins** "
        f"— und **€{saving_after_payoff:.0f}/mo**, sobald die Finanzierung abbezahlt ist.\n\n"
        f"Finanzierung ab €{installment:.0f}/mo, KfW-Förderung von €{subsidy:.0f} "
        f"bereits abgezogen (Netto-Investition €{after_subsidy:.0f})."
    )

    return {
        "explanation_md": explanation_md,
        "upsell_reason_md": upsell_reason_md,
        "proposal_copy_md": proposal_copy_md,
    }


def _explain_en(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate deterministic English prose from payload figures."""
    best: dict[str, Any] = payload.get("best", {})
    monthly_saving = best.get("monthly_saving_eur", 0)
    saving_after_payoff = best.get("saving_after_payoff_eur", 0)
    installment = best.get("installment_eur_month", 0)
    capex = best.get("capex", {})
    after_subsidy = capex.get("after_subsidy_eur", 0)
    subsidy = capex.get("subsidy_eur", 0)
    current_spend = payload.get("current_monthly_spend_eur", 0)
    label = best.get("label", "the full bundle")
    break_even = best.get("break_even_month", 0)

    # 3-sentence English rationale (explanation_md)
    explanation_md = (
        f"With {label} you save €{monthly_saving:.0f}/month from day one, "
        f"compared to your current energy spend of €{current_spend:.0f}/month. "
        f"Once the financing is paid off, your costs drop to just €{saving_after_payoff:.0f}/month "
        f"— permanently, regardless of rising energy prices. "
        f"Break-even is reached in month {break_even}, "
        f"after which every saving is yours to keep."
    )

    # Up-sell nudge (upsell_reason_md)
    upsell: dict[str, Any] = payload.get("upsell", {})
    delta = upsell.get("delta_eur_month", 0)
    upsell_reason_md = (
        f"Adding the final upgrade saves another **€{delta:.0f}/month** "
        f"— a decisive step toward full energy independence."
    )

    # Installer proposal copy (proposal_copy_md) — concise, letter-shaped.
    proposal_copy_md = (
        f"With {label} you save **€{monthly_saving:.0f}/month from day one** "
        f"— and **€{saving_after_payoff:.0f}/month** once the financing is paid off.\n\n"
        f"Financing runs from €{installment:.0f}/month, with the KfW grant of "
        f"€{subsidy:.0f} already deducted (net investment €{after_subsidy:.0f})."
    )

    return {
        "explanation_md": explanation_md,
        "upsell_reason_md": upsell_reason_md,
        "proposal_copy_md": proposal_copy_md,
    }


def _minimal_copy(payload: dict[str, Any], locale: str = "en") -> dict[str, Any]:
    """Absolute minimal copy that will always pass the guard."""
    best = payload.get("best", {})
    monthly_saving = best.get("monthly_saving_eur", 0)
    if locale == "en":
        return {
            "explanation_md": f"The recommended package saves you €{monthly_saving:.0f}/month.",
            "upsell_reason_md": "The next package offers additional savings.",
            "proposal_copy_md": (
                f"**Your energy plan** — saving €{monthly_saving:.0f}/month from day one."
            ),
        }
    return {
        "explanation_md": (f"Das empfohlene Paket spart Ihnen €{monthly_saving:.0f}/mo."),
        "upsell_reason_md": "Das nächste Paket bietet zusätzliche Einsparungen.",
        "proposal_copy_md": (
            f"**Ihr Energieplan** — Einsparung €{monthly_saving:.0f}/mo ab Tag eins."
        ),
    }


# Verify StubAdvisor satisfies the protocol at import time
_: AdvisorLLM = StubAdvisor()