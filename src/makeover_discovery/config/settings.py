"""Typed application configuration.

Settings are validated at startup, so a misconfigured deployment fails loudly on
boot rather than at the first request that happens to need the bad value.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "production"]

PLACEHOLDER_USER_AGENT: Final = "makeover-discovery/0.1 (+https://example.invalid/contact)"
"""Deliberately unusable in production.

Nominatim's usage policy requires a User-Agent that identifies the operator and
offers a way to reach them; an anonymous one gets the IP blocked, so the
production guard below refuses to start with this value still in place.
"""


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

    # --- Outbound providers -------------------------------------------------
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    overpass_base_url: str = "https://overpass-api.de/api"
    user_agent: str = PLACEHOLDER_USER_AGENT
    http_timeout_s: float = Field(default=30.0, gt=0.0, le=300.0)

    # --- Usage-policy compliance -------------------------------------------
    # Both public endpoints ask for roughly one request per second. These are
    # settings rather than constants so a self-hosted mirror can lift them.
    nominatim_min_interval_s: float = Field(default=1.0, ge=0.0)
    overpass_min_interval_s: float = Field(default=1.0, ge=0.0)

    crawl_min_interval_s: float = Field(default=1.0, ge=0.0)
    """Default gap between requests to any one business host."""

    cache_ttl_s: float = Field(default=86_400.0, ge=0.0)
    cache_max_entries: int = Field(default=512, ge=1)

    # --- Enrichment ---------------------------------------------------------
    robots_cache_ttl_s: float = Field(default=86_400.0, ge=0.0)
    enrich_max_businesses: int = Field(default=5, ge=1, le=25)

    use_playwright_fallback: bool = False
    """Off by default: it needs Chromium installed via ``playwright install``,
    a separate step from ``uv sync`` that a fresh checkout has not done."""
    playwright_navigation_timeout_ms: float = Field(default=15_000.0, gt=0.0, le=120_000.0)

    # --- Google Places (optional, behind a flag) -----------------------------
    # OpenStreetMap is the primary, no-key directory; Places sits behind the
    # same BusinessDirectory port for callers who have a key and want it.
    google_places_enabled: bool = False
    google_places_api_key: SecretStr | None = None
    google_places_base_url: str = "https://places.googleapis.com/v1"
    google_places_min_interval_s: float = Field(default=1.0, ge=0.0)

    # --- Search defaults ----------------------------------------------------
    default_search_radius_m: float = Field(default=1_500.0, ge=50.0, le=50_000.0)
    max_search_radius_m: float = Field(default=1_500.0, ge=50.0, le=50_000.0)
    """Ceiling on a radius inferred from a provider bounding box.

    A postcode covers a few streets, but geocoders report a padded box around
    a point result - measured at 7 km for 50450, which pulled in businesses
    from 56000 and 58100. It also bounds the Overpass response, since that
    query is deliberately unlimited."""

    @model_validator(mode="after")
    def _require_real_user_agent_in_production(self) -> Settings:
        if self.environment == "production" and self.user_agent == PLACEHOLDER_USER_AGENT:
            raise ValueError(
                "MAKEOVER_USER_AGENT must identify this deployment and give a contact "
                "address before running against public OpenStreetMap services"
            )
        return self

    @model_validator(mode="after")
    def _require_a_places_key_when_places_is_enabled(self) -> Settings:
        # Fails at boot rather than on the first search: a flag flipped on
        # without a key is a configuration mistake, not a runtime condition.
        if self.google_places_enabled and self.google_places_api_key is None:
            raise ValueError(
                "MAKEOVER_GOOGLE_PLACES_API_KEY is required when "
                "MAKEOVER_GOOGLE_PLACES_ENABLED is set"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings.

    Cached so configuration is read once. Tests override the FastAPI dependency
    rather than mutating this, keeping parallel test runs independent.
    """
    return Settings()
