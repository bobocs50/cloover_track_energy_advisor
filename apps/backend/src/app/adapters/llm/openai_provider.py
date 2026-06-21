"""OpenAI advisor backend (F16 fallback).

Owner: Zhou (backend)
Feature ID: F16 (LLM advisor)

OpenAI fallback when ANTHROPIC_API_KEY is absent.
Number-assertion guard is applied by caller (RecommendationService).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.adapters.llm.base import assert_numbers_grounded
from app.adapters.llm.stub import StubAdvisor

logger = logging.getLogger(__name__)

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
_MAX_RETRIES = 2


class OpenAIAdvisor:
    """AdvisorLLM backed by OpenAI Chat Completions API (F16 fallback)."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._api_key = api_key
        self._model = model

    def explain(self, payload: dict[str, Any], locale: str = "de") -> dict[str, Any]:
        """Call OpenAI in the requested locale; apply number-assertion guard with retries."""
        from app.adapters.llm.claude import _build_prompt, _parse_response

        prompt = _build_prompt(payload, locale)
        for attempt in range(_MAX_RETRIES + 1):
            try:
                raw = self._call_openai(prompt)
                parsed = _parse_response(raw)
                all_text = " ".join(parsed.values())
                if assert_numbers_grounded(all_text, payload):
                    return parsed
                logger.warning("Guard failed on attempt %d", attempt + 1)
            except Exception:
                logger.warning("OpenAI call failed on attempt %d", attempt + 1, exc_info=True)

        logger.error("OpenAI guard failed after retries; using templated fallback")
        return StubAdvisor().explain(payload, locale)

    def _call_openai(self, prompt: str) -> str:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(
                    {
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1024,
                    }
                ),
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])