"""Configuration validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from makeover_discovery.config.settings import PLACEHOLDER_USER_AGENT, Settings

REAL_USER_AGENT = "makeover-discovery/0.1 (+mailto:ops@example.com)"


def test_allows_the_placeholder_user_agent_outside_production():
    settings = Settings(_env_file=None, environment="local")

    assert settings.user_agent == PLACEHOLDER_USER_AGENT


def test_refuses_to_start_in_production_without_a_contactable_user_agent():
    # Nominatim blocks anonymous clients outright, so this has to fail at boot
    # rather than on the first geocode of the day.
    with pytest.raises(ValidationError, match="MAKEOVER_USER_AGENT"):
        Settings(_env_file=None, environment="production")


def test_accepts_production_once_a_real_user_agent_is_configured():
    settings = Settings(_env_file=None, environment="production", user_agent=REAL_USER_AGENT)

    assert settings.user_agent == REAL_USER_AGENT


def test_defaults_to_the_public_provider_endpoints():
    settings = Settings(_env_file=None)

    assert settings.nominatim_base_url.endswith("openstreetmap.org")
    assert settings.overpass_base_url.endswith("/api")


def test_rejects_a_non_positive_http_timeout():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, http_timeout_s=0.0)
