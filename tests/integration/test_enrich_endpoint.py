"""The POST /enrich endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichBusinessProfile,
)
from makeover_discovery.domain.model.web import ExtractedContent
from makeover_discovery.domain.policy.redaction import RedactionPolicy
from makeover_discovery.domain.policy.retention import RetentionPolicy
from makeover_discovery.interfaces.api.app import create_app
from makeover_discovery.interfaces.api.deps import provide_enrich_business_profile
from tests.fakes.candidates import make_candidate
from tests.fakes.clock import FixedClock
from tests.fakes.web import FakeExtractor, FakeWebFetcher, ForbiddenWebFetcher, make_page

HTTP_OK = 200
HTTP_UNPROCESSABLE = 422

CONTENT = ExtractedContent(descriptors=("halal",), photo_urls=("https://cdn.example/a.jpg",))
PAYLOAD = make_candidate(website="https://ali.example").model_dump(mode="json")


def client_for(use_case: EnrichBusinessProfile) -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_enrich_business_profile] = lambda: use_case
    return TestClient(app)


def build(fetcher, content=None) -> EnrichBusinessProfile:
    return EnrichBusinessProfile(
        fetcher=fetcher,
        extractor=FakeExtractor(content),
        clock=FixedClock(),
        retention=RetentionPolicy(),
        redaction=RedactionPolicy(),
    )


@pytest.fixture
def client() -> TestClient:
    return client_for(build(FakeWebFetcher(make_page()), CONTENT))


def test_returns_the_enriched_profile(client):
    response = client.post("/enrich", json=PAYLOAD)

    assert response.status_code == HTTP_OK
    assert response.json()["profile"]["name"]["value"] == "Kedai Kopi Ali"


def test_every_profile_field_carries_its_source(client):
    # The wire format has to preserve provenance, or the compliance guarantee
    # stops at the process boundary.
    body = response_body(client)

    assert body["profile"]["name"]["source"]["license"] == "odbl-1.0"
    assert body["profile"]["descriptors"][0]["source"]["source"] == "business_website"


def test_returns_the_attribution_the_caller_must_display(client):
    assert response_body(client)["attributions"] == ["© OpenStreetMap contributors"]


def test_reports_that_the_website_was_read(client):
    assert response_body(client)["website_outcome"] == "fetched"


def test_reports_a_robots_refusal_rather_than_an_empty_profile():
    client = client_for(build(ForbiddenWebFetcher()))

    body = client.post("/enrich", json=PAYLOAD).json()

    assert body["website_outcome"] == "robots_denied"
    assert body["profile"]["descriptors"] == []


def test_rejects_a_candidate_that_is_not_well_formed(client):
    response = client.post("/enrich", json={"name": "Kedai"})

    assert response.status_code == HTTP_UNPROCESSABLE


def response_body(client: TestClient) -> dict:
    return client.post("/enrich", json=PAYLOAD).json()
