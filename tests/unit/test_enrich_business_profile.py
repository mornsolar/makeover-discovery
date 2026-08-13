"""The enrichment use case."""

from __future__ import annotations

from makeover_contracts.provenance import DataSource

from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichBusinessProfile,
    WebsiteOutcome,
)
from makeover_discovery.domain.model.web import ExtractedContent
from makeover_discovery.domain.policy.redaction import RedactionPolicy
from makeover_discovery.domain.policy.retention import RetentionPolicy
from tests.fakes.candidates import make_candidate
from tests.fakes.clock import FixedClock
from tests.fakes.web import (
    FakeExtractor,
    FakeWebFetcher,
    ForbiddenWebFetcher,
    make_page,
)

WEBSITE = "https://ali.example"
RICH_CONTENT = ExtractedContent(
    name="Kedai Kopi Ali Sdn Bhd",
    description="Traditional kopitiam since 1968.",
    phone="+60 3-1234 5678",
    descriptors=("Hainanese", "halal", "Halal"),
    photo_urls=("https://cdn.example/a.jpg",),
)


def build(fetcher, content: ExtractedContent | None = None) -> EnrichBusinessProfile:
    return EnrichBusinessProfile(
        fetcher=fetcher,
        extractor=FakeExtractor(content),
        clock=FixedClock(),
        retention=RetentionPolicy(),
        redaction=RedactionPolicy(),
    )


async def test_reports_when_the_business_lists_no_website():
    result = await build(FakeWebFetcher()).execute(make_candidate())

    assert result.website_outcome is WebsiteOutcome.NOT_LISTED


async def test_still_produces_a_profile_without_a_website():
    result = await build(FakeWebFetcher()).execute(make_candidate())

    assert result.profile.name.value == "Kedai Kopi Ali"
    assert result.profile.descriptors == ()


async def test_reports_a_robots_refusal_distinctly_from_an_empty_site():
    # Collapsing "we were forbidden" into "there was nothing there" would hide
    # a compliance decision behind an ordinary-looking empty profile.
    candidate = make_candidate(website=WEBSITE)

    result = await build(ForbiddenWebFetcher()).execute(candidate)

    assert result.website_outcome is WebsiteOutcome.ROBOTS_DENIED


async def test_reports_an_unreachable_site():
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(None)).execute(candidate)

    assert result.website_outcome is WebsiteOutcome.UNAVAILABLE


async def test_reports_a_site_that_yielded_nothing():
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), ExtractedContent()).execute(candidate)

    assert result.website_outcome is WebsiteOutcome.EMPTY


async def test_takes_descriptors_and_photos_from_the_website():
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), RICH_CONTENT).execute(candidate)

    assert [d.value for d in result.profile.descriptors] == ["Hainanese", "halal"]
    assert [p.value for p in result.profile.photo_urls] == ["https://cdn.example/a.jpg"]


async def test_attributes_website_fields_to_the_website_not_the_directory():
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), RICH_CONTENT).execute(candidate)

    assert result.profile.descriptors[0].source.source is DataSource.BUSINESS_WEBSITE
    assert result.profile.name.source.source is DataSource.OPENSTREETMAP


async def test_keeps_the_directory_name_over_the_websites():
    # The directory name is what the search matched on; replacing it would
    # break the link back to the candidate the user picked.
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), RICH_CONTENT).execute(candidate)

    assert result.profile.name.value == "Kedai Kopi Ali"


async def test_strips_contact_details_out_of_scraped_descriptors():
    content = ExtractedContent(descriptors=("wifi ali@example.com",))
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), content).execute(candidate)

    # The descriptor survives, minus the address: redaction removes contact
    # details, it does not discard whatever they were attached to.
    assert [d.value for d in result.profile.descriptors] == ["wifi"]


async def test_drops_a_descriptor_that_was_only_a_contact_detail():
    content = ExtractedContent(descriptors=("ali@example.com",))
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), content).execute(candidate)

    assert result.profile.descriptors == ()


async def test_does_not_keep_a_phone_number_scraped_from_prose():
    content = ExtractedContent(phone="+60 3-1234 5678")
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), content).execute(candidate)

    assert result.profile.phone is None


async def test_fetches_the_websites_listed_on_the_candidate():
    fetcher = FakeWebFetcher(make_page())
    candidate = make_candidate(website=WEBSITE)

    await build(fetcher, RICH_CONTENT).execute(candidate)

    assert fetcher.urls == [WEBSITE]


async def test_gives_the_profile_a_stable_contract_slug():
    result = await build(FakeWebFetcher()).execute(make_candidate(external_id="node/7"))

    assert result.profile.id.startswith("kedai-kopi-ali-")


async def test_reports_the_attribution_the_profile_obliges():
    candidate = make_candidate(website=WEBSITE)

    result = await build(FakeWebFetcher(make_page()), RICH_CONTENT).execute(candidate)

    assert "© OpenStreetMap contributors" in result.profile.attributions()
