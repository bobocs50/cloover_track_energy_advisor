"""Application settings (pydantic-settings).

Owner: Zhou (backend)
Feature ID: F01 (monorepo scaffold)

All secret keys are loaded here from this app's env — never the frontend.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime configuration sourced from `.env` / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    tavily_api_key: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    google_solar_api_key: str = ""
    google_geocoding_api_key: str = ""
    # NoDecode: stop pydantic-settings from JSON-decoding the raw env value for
    # this list field. Without it, a plain `CORS_ORIGINS=http://localhost:5173`
    # (not JSON) raises a SettingsError before the validator below can run.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    app_env: str = "dev"
    # Live-run demo throttle: ms of artificial delay between streamed pipeline events
    # so each step is legible in the activity feed. 0 = off (real speed).
    demo_pacing_ms: int = 0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Parse CORS_ORIGINS from env as either a JSON array or a comma-separated list.

        Both `CORS_ORIGINS=http://localhost:5173,http://localhost:5180` and
        `CORS_ORIGINS=["http://localhost:5173"]` are accepted. (NoDecode disables
        pydantic-settings' own JSON decode, so without the JSON branch a `[...]`
        value would be mis-split into one bogus origin that matches no browser.)
        """
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                import json

                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in text.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()