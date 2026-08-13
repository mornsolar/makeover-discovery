from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from makeover_contracts.version import CONTRACT_VERSION

from makeover_discovery.config.settings import Settings, get_settings
from makeover_discovery.interfaces.api.app import create_app
from makeover_discovery.interfaces.api.deps import provide_clock
from tests.fakes.clock import FixedClock

FIXED_INSTANT = datetime(2026, 8, 13, 9, 30, tzinfo=UTC)


def build_client() -> TestClient:
    """Build an app with the clock and settings overridden.

    Proves the composition root is genuinely injectable: no adapter is reached
    through a module-level singleton.
    """
    app = create_app()
    app.dependency_overrides[provide_clock] = lambda: FixedClock(FIXED_INSTANT)
    app.dependency_overrides[get_settings] = lambda: Settings(environment="test")
    return TestClient(app)


class TestHealthEndpoint:
    def test_returns_ok(self):
        response = build_client().get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_reports_the_contract_version(self):
        response = build_client().get("/health")
        assert response.json()["contract_version"] == CONTRACT_VERSION

    def test_uses_the_injected_clock(self):
        response = build_client().get("/health")
        # Compare instants, not strings: pydantic emits "...Z" where
        # datetime.isoformat() emits "...+00:00" for the same moment.
        assert datetime.fromisoformat(response.json()["checked_at"]) == FIXED_INSTANT

    def test_uses_the_injected_settings(self):
        response = build_client().get("/health")
        assert response.json()["environment"] == "test"

    def test_exposes_an_openapi_document(self):
        response = build_client().get("/openapi.json")
        assert response.status_code == 200
        assert "/health" in response.json()["paths"]
