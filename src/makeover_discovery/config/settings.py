"""Typed application configuration.

Settings are validated at startup, so a misconfigured deployment fails loudly on
boot rather than at the first request that happens to need the bad value.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "production"]


class Settings(BaseSettings):
    """Configuration for the discovery service."""

    model_config = SettingsConfigDict(
        env_prefix="MAKEOVER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "local"
    service_name: str = "makeover-discovery"
    log_level: str = "INFO"

    # Populated from Phase 5 onward; absent means the render service is not
    # wired up yet, which is a valid state for Phases 1-3.
    render_service_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings.

    Cached so configuration is read once. Tests override the FastAPI dependency
    rather than mutating this, keeping parallel test runs independent.
    """
    return Settings()
