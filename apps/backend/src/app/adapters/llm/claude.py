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


def _build_prompt(payload: dict[str, Any], locale: str = "de") -> str:
    best = payload.get("best", {})
    monthly_saving = best.get("monthly_saving_eur", 0)
    saving_after_payoff = best.get("saving_after_payoff_eur", 0)
    installment = best.get("installment_eur_month", 0)
    current_spend = payload.get("current_monthly_spend_eur", 0)

    if locale == "en":
        return f"""You are an energy advisor for the Heimwende platform. Write prose in English.
IMPORTANT: Do NOT calculate any numbers yourself. Use ONLY the following values from the payload:
- Current monthly spend: €{current_spend:.0f}/month
- Monthly saving (from day one): €{monthly_saving:.0f}/month
- Monthly saving (after financing ends): €{saving_after_payoff:.0f}/month
- Monthly installment: €{installment:.0f}/month

Return exactly three sections in JSON format:
{{
  "explanation_md": "<3-sentence English rationale using only the numbers above>",
  "upsell_reason_md": "<1-2 sentence upgrade recommendation in English>",
  "proposal_copy_md": "<Markdown proposal copy in English for the installer>"
}}

Use EXCLUSIVELY the provided numeric values. Do not invent new numbers."""

    return f"""Du bist ein Energieberater der Heimwende-Plattform. Schreibe Prosa auf Deutsch.
WICHTIG: Berechne KEINE Zahlen selbst. Verwende NUR die folgenden Werte aus dem Payload:
- Aktuelle Kosten: €{current_spend:.0f}/mo
- Monatliche Einsparung (ab Tag 1): €{monthly_saving:.0f}/mo
- Monatliche Einsparung (nach Kreditende): €{saving_after_payoff:.0f}/mo
- Monatliche Rate: €{installment:.0f}/mo

Erstelle drei Abschnitte im JSON-Format:
{{
  "explanation_md": "<3 Sätze Rationale auf Deutsch, genau die oben genannten Zahlen>",
  "upsell_reason_md": "<1-2 Sätze Upgrade-Empfehlung>",
  "proposal_copy_md": "<Markdown Angebotstext für den Installer>"
}}

Verwende AUSSCHLIESSLICH die angegebenen Zahlenwerte. Erfinde keine neuen Zahlen."""


def _parse_response(raw: str) -> dict[str, Any]:
    """Extract the JSON object from the Claude response."""
    import re

    match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if match:
        return dict(json.loads(match.group()))
    raise ValueError(f"Could not parse JSON from Claude response: {raw[:200]}")