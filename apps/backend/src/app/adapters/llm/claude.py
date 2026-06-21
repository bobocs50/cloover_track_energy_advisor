"""Claude (Anthropic) advisor backend (F16).

Owner: Zhou (backend)
Feature ID: F16 (LLM advisor)

Uses the Anthropic Messages API via httpx (no anthropic SDK dependency needed).
Number-assertion guard is applied by the caller (RecommendationService).
Model: claude-opus-4-8 (§16 D8).

IMPORTANT: This provider is only instantiated when ANTHROPIC_API_KEY is set.
The key must never appear in any client-side payload (§11).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.adapters.llm.base import assert_numbers_grounded
from app.adapters.llm.stub import StubAdvisor

logger = logging.getLogger(__name__)

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_MAX_RETRIES = 2


class ClaudeAdvisor:
    """AdvisorLLM backed by Claude (Anthropic Messages API).

    Falls back to the templated StubAdvisor copy on guard failure after
    bounded retries, so the pipeline never ships an unverified figure (AC4).
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-8") -> None:
        self._api_key = api_key
        self._model = model

    def explain(self, payload: dict[str, Any], locale: str = "de") -> dict[str, Any]:
        """Call Claude to generate prose in the requested locale; apply number-assertion guard."""
        prompt = _build_prompt(payload, locale)
        for attempt in range(_MAX_RETRIES + 1):
            try:
                raw = self._call_claude(prompt)
                parsed = _parse_response(raw)
                all_text = " ".join(parsed.values())
                if assert_numbers_grounded(all_text, payload):
                    return parsed
                logger.warning("Guard failed on attempt %d — retrying", attempt + 1)
            except Exception:
                logger.warning("Claude call failed on attempt %d", attempt + 1, exc_info=True)

        # Retries exhausted — fall back to deterministic templated copy (AC4)
        logger.error(
            "Claude guard failed after %d retries; using templated fallback",
            _MAX_RETRIES + 1,
        )
        return StubAdvisor().explain(payload, locale)

    def _call_claude(self, prompt: str) -> str:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _ANTHROPIC_API_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                content=json.dumps(
                    {
                        "model": self._model,
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["content"][0]["text"])


def _build_prompt(payload: dict[str, Any], locale: str = "en") -> str:
    best = payload.get("best", {})
    monthly_saving = best.get("monthly_saving_eur", 0)
    saving_after_payoff = best.get("saving_after_payoff_eur", 0)
    installment = best.get("installment_eur_month", 0)
    current_spend = payload.get("current_monthly_spend_eur", 0)

    context = payload.get("household_context") or {}
    tiers = payload.get("tiers") or []
    tier_lines = "\n".join(
        f"- {t.get('id')}: {t.get('name')} ({t.get('label')})" for t in tiers
    )

    if locale == "en":
        context_block = ""
        if context:
            lines = "\n".join(f"- {v}" for v in context.values())
            context_block = (
                "\nThis specific household's situation — reason about WHY this upgrade "
                "fits them (e.g. an ageing heat pump worth replacing for the subsidy). "
                "Refer to it qualitatively; do NOT introduce any new € amounts:\n"
                f"{lines}\n"
            )
        tier_block = ""
        tier_json = ""
        if tier_lines:
            tier_block = (
                "\nThree packaged offer cards are shown below. Write a one-sentence rationale "
                "for each — what it includes and who it suits. The cards already display every "
                "€ figure, so write NO € amounts in these three:\n"
                f"{tier_lines}\n"
            )
            tier_json = (
                ',\n  "tier_rationale_low": "<one sentence, NO € amounts>",'
                '\n  "tier_rationale_middle": "<one sentence, NO € amounts>",'
                '\n  "tier_rationale_high": "<one sentence, NO € amounts>"'
            )
        return f"""You are an energy advisor for the Heimwende platform. Write prose in English.
IMPORTANT: Do NOT calculate any numbers yourself. Use ONLY the following values from the payload:
- Current monthly spend: €{current_spend:.0f}/month
- Monthly saving (from day one): €{monthly_saving:.0f}/month
- Monthly saving (after financing ends): €{saving_after_payoff:.0f}/month
- Monthly installment: €{installment:.0f}/month
{context_block}{tier_block}
Return JSON with exactly these keys:
{{
  "explanation_md": "<3 sentences linking the saving to this household; only € numbers above>",
  "upsell_reason_md": "<1-2 sentence upgrade recommendation in English>",
  "proposal_copy_md": "<Markdown proposal copy in English for the installer>"{tier_json}
}}

Use EXCLUSIVELY the provided numeric values. Do not invent new numbers."""

    context_block = ""
    if context:
        lines = "\n".join(f"- {v}" for v in context.values())
        context_block = (
            "\nSituation dieses Haushalts — begründe, WARUM dieses Upgrade passt "
            "(z. B. eine alte Wärmepumpe, deren Austausch sich wegen der Förderung lohnt). "
            "Beziehe dich qualitativ darauf; führe KEINE neuen €-Beträge ein:\n"
            f"{lines}\n"
        )
    tier_block = ""
    tier_json = ""
    if tier_lines:
        tier_block = (
            "\nUnten stehen drei Angebotskarten. Schreibe für jede einen Ein-Satz-Grund — was "
            "sie enthält und für wen sie passt. Die Karten zeigen bereits alle €-Beträge, "
            "schreibe daher KEINE €-Beträge in diese drei:\n"
            f"{tier_lines}\n"
        )
        tier_json = (
            ',\n  "tier_rationale_low": "<ein Satz, KEINE €-Beträge>",'
            '\n  "tier_rationale_middle": "<ein Satz, KEINE €-Beträge>",'
            '\n  "tier_rationale_high": "<ein Satz, KEINE €-Beträge>"'
        )
    return f"""Du bist ein Energieberater der Heimwende-Plattform. Schreibe Prosa auf Deutsch.
WICHTIG: Berechne KEINE Zahlen selbst. Verwende NUR die folgenden Werte aus dem Payload:
- Aktuelle Kosten: €{current_spend:.0f}/mo
- Monatliche Einsparung (ab Tag 1): €{monthly_saving:.0f}/mo
- Monatliche Einsparung (nach Kreditende): €{saving_after_payoff:.0f}/mo
- Monatliche Rate: €{installment:.0f}/mo
{context_block}{tier_block}
Gib JSON mit genau diesen Schlüsseln zurück:
{{
  "explanation_md": "<3 Sätze: Einsparung mit Haushaltssituation verknüpfen; nur €-Zahlen oben>",
  "upsell_reason_md": "<1-2 Sätze Upgrade-Empfehlung>",
  "proposal_copy_md": "<Markdown Angebotstext für den Installer>"{tier_json}
}}

Verwende AUSSCHLIESSLICH die angegebenen Zahlenwerte. Erfinde keine neuen Zahlen."""


def _parse_response(raw: str) -> dict[str, Any]:
    """Extract the JSON object from the Claude response."""
    import re

    match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if match:
        return dict(json.loads(match.group()))
    raise ValueError(f"Could not parse JSON from Claude response: {raw[:200]}")