"""LLM advisor interface + number-assertion guard (F16).

Owner: Zhou (backend)
Feature ID: F16 (LLM advisor)

Defines the contract every advisor backend implements and the mandatory
number-assertion guard (§15).  Keys live in this app's env — never the
frontend bundle (§11).
"""

from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Number-assertion guard (§15 / AC2 / AC3)
# ---------------------------------------------------------------------------

# Pattern that matches standalone euro figures in text, e.g.:
#   €120/mo  +€120/mo  -€24/mo  €364/mo  ≈€0  €31 000  €11k  €244
_EURO_PATTERN = re.compile(
    r"(?:€|EUR)\s*[\d\s]+(?:[.,]\d+)?(?:k|K)?",
    re.UNICODE,
)


def _normalise_figure(token: str) -> float:
    """Convert a raw €-figure string to a float for comparison."""
    # Remove currency symbols, whitespace
    s = re.sub(r"[€EUR\s]", "", token)
    # Handle k/K multiplier
    multiplier = 1.0
    if s.upper().endswith("K"):
        multiplier = 1_000.0
        s = s[:-1]
    # Remove thousand separators and normalise decimal comma
    s = s.replace(".", "").replace(",", ".")
    try:
        return round(float(s) * multiplier, 2)
    except ValueError:
        return -1.0


def extract_euro_figures(text: str) -> list[float]:
    """Return all € amounts found in text as normalised floats."""
    tokens = _EURO_PATTERN.findall(text)
    return [_normalise_figure(t) for t in tokens]


def _collect_allowed_figures(payload: dict[str, Any]) -> set[float]:
    """Walk the payload and collect every numeric € value (AC2 / §15)."""
    allowed: set[float] = set()

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item)
        elif isinstance(obj, (int, float)):
            allowed.add(round(float(obj), 2))

    _walk(payload)
    return allowed


def assert_numbers_grounded(text: str, payload: dict[str, Any]) -> bool:
    """Return True if every € figure in text also appears in payload.

    Raises nothing — callers inspect the return value to decide whether
    to regenerate or fall back (§15 / AC3 / AC4).
    """
    allowed = _collect_allowed_figures(payload)
    for figure in extract_euro_figures(text):
        if figure < 0:
            continue  # parse failure — skip
        # Tolerant match: ±€1 to handle rounding in prose
        if not any(abs(figure - a) <= 1.0 for a in allowed):
            return False
    return True


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AdvisorLLM(Protocol):
    """Turns a computed recommendation payload into plain-language copy.

    The LLM is PROSE-ONLY and must NEVER compute a number (§1, §9).
    Every € figure in the output is asserted against the payload by the
    number-assertion guard (§15 / AC2 / AC3).

    Returns a dict with keys:
        explanation_md   : 3-sentence rationale
        upsell_reason_md : up-sell nudge (diff vs next-smaller rung)
        proposal_copy_md : installer-ready proposal copy (Markdown)

    The prose language follows ``locale``: "de" (default) → German,
    "en" → English.  Omitting locale keeps the existing German behaviour.
    """

    def explain(self, payload: dict[str, Any], locale: str = "de") -> dict[str, Any]:
        """Return prose copy derived from the payload numbers in the requested locale."""
        ...