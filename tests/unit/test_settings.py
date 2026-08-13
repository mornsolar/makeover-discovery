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


def test_refuses_to_start_in_production_without_a_brief_model_key():
    # A production deployment that cannot generate a brief is broken; saying so
    # at boot beats discovering it on the first paid request.
    with pytest.raises(ValidationError, match="MAKEOVER_ANTHROPIC_API_KEY"):
        Settings(_env_file=None, environment="production", user_agent=REAL_USER_AGENT)


def test_accepts_production_once_it_is_fully_configured():
    settings = Settings(
        _env_file=None,
        environment="production",
        user_agent=REAL_USER_AGENT,
        anthropic_api_key="sk-test",
    )

    assert settings.user_agent == REAL_USER_AGENT


def test_needs_no_model_key_outside_production():
    # Discovery and enrichment are useful on their own; only the brief needs it.
    assert Settings(_env_file=None).anthropic_api_key is None


def test_defaults_to_the_current_opus_model():
    assert Settings(_env_file=None).anthropic_model == "claude-opus-5"


def test_does_not_expose_the_model_key_through_repr():
    settings = Settings(_env_file=None, anthropic_api_key="sk-secret")

    assert settings.anthropic_api_key is not None
    assert "sk-secret" not in repr(settings.anthropic_api_key)


def test_allows_exactly_one_repair_round_by_default():
    # More rounds mostly buy latency and tokens once the model has been handed
    # the exact list of what was wrong.
    assert Settings(_env_file=None).brief_max_repair_attempts == 1


def test_defaults_to_the_public_provider_endpoints():
    settings = Settings(_env_file=None)

    assert settings.nominatim_base_url.endswith("openstreetmap.org")
    assert settings.overpass_base_url.endswith("/api")


def test_rejects_a_non_positive_http_timeout():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, http_timeout_s=0.0)


def test_disables_google_places_by_default():
    settings = Settings(_env_file=None)

    assert settings.google_places_enabled is False
    assert settings.google_places_api_key is None


def test_refuses_to_start_with_places_enabled_and_no_key():
    # A flag flipped on without a key is a configuration mistake, not a
    # runtime condition to discover on the first search.
    with pytest.raises(ValidationError, match="MAKEOVER_GOOGLE_PLACES_API_KEY"):
        Settings(_env_file=None, google_places_enabled=True)


def test_accepts_places_enabled_once_a_key_is_configured():
    settings = Settings(_env_file=None, google_places_enabled=True, google_places_api_key="k")

    assert settings.google_places_api_key is not None
    assert settings.google_places_api_key.get_secret_value() == "k"


def test_does_not_expose_the_places_key_through_repr():
    # SecretStr keeps the key out of logs and error messages, not just out of
    # source control.
    settings = Settings(_env_file=None, google_places_enabled=True, google_places_api_key="k")

    assert "k" not in repr(settings.google_places_api_key)


def test_disables_the_playwright_fallback_by_default():
    # It needs a Chromium binary that `uv sync` does not install; defaulting
    # to on would break a fresh checkout that has not run `playwright install`.
    settings = Settings(_env_file=None)

    assert settings.use_playwright_fallback is False
