"""Advisor LLM factory (F16).

Owner: Zhou (backend)
Feature ID: F16 (LLM advisor)

Selection policy (§1, §11, §16 D8):
  - ``app_env == "dev"`` OR no API keys present → StubAdvisor (offline safe).
  - Anthropic API key present → Claude backend (model claude-opus-4-8).
  - Only OpenAI key present → OpenAI fallback (number guard still gates output).
  - Default (fallback) → StubAdvisor.

All keys come from settings (this app's env) — never the frontend bundle.
"""

from __future__ import annotations

import logging

from app.adapters.llm.base import AdvisorLLM
from app.adapters.llm.stub import StubAdvisor
from app.core.config import Settings

logger = logging.getLogger(__name__)

# Real-provider model IDs (§16 D8)
_CLAUDE_MODEL = "claude-opus-4-8"
_OPENAI_MODEL = "gpt-4o"


def make_advisor(settings: Settings) -> AdvisorLLM:
    """Pick an AdvisorLLM implementation from settings.

    Default is StubAdvisor (offline / dev).  If a real API key is configured
    and app_env != "dev", attempt to load the Claude or OpenAI backend.
    The number-assertion guard is applied by the caller (RecommendationService)
    regardless of which provider is selected (§15).
    """
    if settings.app_env == "dev":
        logger.debug("app_env=dev — using StubAdvisor (offline)")
        return StubAdvisor()

    if settings.anthropic_api_key:
        try:
            return _make_claude_advisor(settings)
        except Exception:
            logger.warning("Claude advisor unavailable; falling back to StubAdvisor", exc_info=True)

    if settings.openai_api_key:
        try:
            return _make_openai_advisor(settings)
        except Exception:
            logger.warning("OpenAI advisor unavailable; falling back to StubAdvisor", exc_info=True)

    logger.debug("No LLM API key — using StubAdvisor")
    return StubAdvisor()


def _make_claude_advisor(settings: Settings) -> AdvisorLLM:
    """Build a Claude (Anthropic) advisor backend."""
    from app.adapters.llm.claude import ClaudeAdvisor

    return ClaudeAdvisor(api_key=settings.anthropic_api_key, model=_CLAUDE_MODEL)


def _make_openai_advisor(settings: Settings) -> AdvisorLLM:
    """Build an OpenAI advisor backend."""
    from app.adapters.llm.openai_provider import OpenAIAdvisor

    return OpenAIAdvisor(api_key=settings.openai_api_key, model=_OPENAI_MODEL)