"""FastAPI dependency providers.

Owner: Zhou (backend)
Feature ID: F17 (api endpoints) — resolver wiring F12

Dependencies the routes/services inject. Request-scoped pricing is resolved per
PLZ via the F12 Resolver; the live route (RecommendationService) resolves it from
the request's household.plz.
"""

from __future__ import annotations

from typing import Any

from app.adapters.resolver import Resolver
from app.adapters.supabase import get_supabase_client
from app.core.config import get_settings
from app.domain.models import PricingContext

__all__ = ["get_settings", "get_pricing_context", "get_db"]


def get_pricing_context(plz: str) -> PricingContext:
    """Resolve the PricingContext for a request's PLZ from price_catalog (F12).

    Offline-safe: the Resolver falls back to the seeded catalog when no DB is
    configured. The pure engine imports no price — this is the injection seam.
    """
    ctx, _assumptions = Resolver().resolve_pricing(plz)
    return ctx


def get_db() -> Any:
    """Return the server-side Supabase PostgREST client."""
    return get_supabase_client()