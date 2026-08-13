"""The POST /brief endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from makeover_discovery.application.use_cases.generate_design_brief import GenerateDesignBrief
from makeover_discovery.domain.model.brief import MANDATORY_EXCLUSIONS
from makeover_discovery.infrastructure.llm.pricing import DEFAULT_MODEL, pricing_for
from makeover_discovery.interfaces.api.app import create_app
from makeover_discovery.interfaces.api.deps import provide_generate_design_brief
from tests.fakes.brief import FakeBriefGenerator, FakeCapabilitySource, make_brief, make_profile

HTTP_OK = 200
HTTP_UNPROCESSABLE = 422
HTTP_BAD_GATEWAY = 502

PAYLOAD = make_profile().model_dump(mode="json")


def client_for(generator: FakeBriefGenerator) -> TestClient:
    app = create_app()
    app.dependency_overrides[provide_generate_design_brief] = lambda: GenerateDesignBrief(
        generator=generator,
        capabilities=FakeCapabilitySource(),
        pricing=pricing_for(DEFAULT_MODEL),
    )
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return client_for(FakeBriefGenerator())


def body(client: TestClient) -> dict:
    return client.post("/brief", json=PAYLOAD).json()


def test_returns_a_brief_for_the_profile(client):
    response = client.post("/brief", json=PAYLOAD)

    assert response.status_code == HTTP_OK
    assert response.json()["brief"]["business_id"] == "kedai-kopi-ali-node-1"


def test_reports_what_the_brief_cost(client):
    # Cost travels with the artifact rather than only into a log, so a caller
    # can attribute spend to the business that caused it.
    usage = body(client)["usage"]

    assert usage["input_tokens"] > 0
    assert usage["estimated_cost_usd"] > 0


def test_carries_the_ai_disclosure_constraints(client):
    assert set(MANDATORY_EXCLUSIONS) <= set(body(client)["brief"]["do_not_include"])


def test_repeats_the_attribution_the_profile_licences_require(client):
    # Anything rendered from this brief still displays the profile's credits.
    assert body(client)["attributions"] == ["© OpenStreetMap contributors"]


def test_records_the_prompt_version_that_produced_it(client):
    assert body(client)["brief"]["generation"]["prompt_version"] == "brief-v1"


def test_reports_a_model_that_cannot_produce_a_usable_brief():
    client = client_for(FakeBriefGenerator([make_brief(camera_move="barrel_roll")]))

    response = client.post("/brief", json=PAYLOAD)

    assert response.status_code == HTTP_BAD_GATEWAY


def test_rejects_a_profile_that_is_not_well_formed(client):
    assert client.post("/brief", json={"id": "x"}).status_code == HTTP_UNPROCESSABLE
