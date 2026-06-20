"""FastAPI dependency providers.

Owner: Zhou (backend)
Feature ID: F17 (api endpoints)

Placeholder dependencies the routes inject. Fill in as features land.
"""

from __future__ import annotations

from typing import Any

from app.adapters.supabase import get_supabase_client
from app.core.config import get_settings

__all__ = ["get_settings", "get_pricing_context", "get_db"]


def get_pricing_context() -> Any:
    """Resolve the PricingContext for a request.

    TODO F12: build via adapters.resolver.Resolver from price_catalog.
    """
    raise NotImplementedError("TODO F12: pricing context dependency")


def get_db() -> Any:
    """Return the server-side Supabase PostgREST client."""
    return get_supabase_client()
