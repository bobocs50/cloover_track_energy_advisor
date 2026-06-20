"""Supabase PostgREST client provider.

Owner: Zhou (backend)
Feature ID: F04 (supabase price catalog)

Uses the SERVICE_ROLE key from settings — server-side only.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings, get_settings


def get_supabase_client(settings: Settings | None = None) -> httpx.Client:
    """Return a configured PostgREST client without making a network request."""
    resolved = settings or get_settings()
    if not resolved.supabase_url or not resolved.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for database access"
        )

    return httpx.Client(
        base_url=f"{resolved.supabase_url.rstrip('/')}/rest/v1",
        headers={
            "apikey": resolved.supabase_service_role_key,
            "Authorization": f"Bearer {resolved.supabase_service_role_key}",
            "Accept": "application/json",
        },
        timeout=10.0,
    )
