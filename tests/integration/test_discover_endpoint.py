"""The POST /discover endpoint.

Adapters are replaced through the composition root's dependency, which is the
same seam production uses - so what is exercised here is real routing, real
validation, and real error translation over fake providers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.interfaces.api.app import create_app
from makeover_discovery.interfaces.api.deps import provide_discover_businesses
from tests.fakes.candidates import make_candidate
from tests.fakes.directory import FakeBusinessDirectory
from tests.fakes.geocoder import FailingGeocoder, FakeGeocoder

REQUEST = {"postcode": "50450", "country": "MY"}
HTTP_OK = 200
HTTP_UNPROCESSABLE = 422
HTTP_NOT_FOUND = 404
HTTP_BAD_GATEWAY = 502


def client_for(use_case: DiscoverBusinesses) -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_discover_businesses] = lambda: use_case
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    directory = FakeBusinessDirectory((make_candidate(),))
    return client_for(DiscoverBusinesses(FakeGeocoder(), directory))


def test_returns_the_discovered_businesses(client):
    response = client.post("/discover", json=REQUEST)

    assert response.status_code == HTTP_OK
    assert [item["name"] for item in response.json()["candidates"]] == ["Kedai Kopi Ali"]


def test_returns_the_attribution_the_caller_must_display(client):
    response = client.post("/discover", json=REQUEST)

    assert response.json()["attributions"] == ["© OpenStreetMap contributors"]


def test_echoes_the_area_that_was_searched(client):
    response = client.post("/discover", json=REQUEST)

    assert response.json()["area"]["kind"] == "circle"


def test_reports_an_unknown_postcode_as_not_found(client):
    response = client.post("/discover", json={"postcode": "99999", "country": "MY"})

    assert response.status_code == HTTP_NOT_FOUND
    assert response.json()["error"] == "NotFoundError"


def test_reports_a_postcode_of_the_wrong_shape_as_unprocessable(client):
    # Five digits is the Malaysian format; "5045" must not reach a provider.
    response = client.post("/discover", json={"postcode": "5045", "country": "MY"})

    assert response.status_code == HTTP_UNPROCESSABLE


def test_rejects_an_unknown_field(client):
    response = client.post("/discover", json={**REQUEST, "radius": 5000})

    assert response.status_code == HTTP_UNPROCESSABLE


def test_rejects_a_limit_above_the_ceiling(client):
    response = client.post("/discover", json={**REQUEST, "limit": 5000})

    assert response.status_code == HTTP_UNPROCESSABLE


def test_reports_a_provider_outage_as_a_bad_gateway():
    # 502, not 500: the distinction tells an operator whose logs to read.
    use_case = DiscoverBusinesses(FailingGeocoder(), FakeBusinessDirectory())

    response = client_for(use_case).post("/discover", json=REQUEST)

    assert response.status_code == HTTP_BAD_GATEWAY
    assert response.json()["error"] == "UpstreamError"


def test_passes_the_requested_category_through_to_the_directory():
    directory = FakeBusinessDirectory()
    use_case = DiscoverBusinesses(FakeGeocoder(), directory)

    client_for(use_case).post("/discover", json={**REQUEST, "categories": ["cafe"]})

    assert directory.calls[0][1].categories == ("cafe",)
