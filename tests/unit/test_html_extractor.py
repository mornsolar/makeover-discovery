"""HTML and JSON-LD extraction."""

from __future__ import annotations

from makeover_discovery.infrastructure.extract.html_extractor import HtmlContentExtractor
from tests.fakes.web import make_page

extractor = HtmlContentExtractor()

JSON_LD_PAGE = """
<html><head><title>Kedai Kopi Ali | Kuala Lumpur</title>
<meta property="og:image" content="/img/shop.jpg">
<meta name="keywords" content="halal, kopitiam">
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@type":"WebSite","name":"Some Site"},
 {"@type":"CafeOrCoffeeShop","name":"Kedai Kopi Ali",
  "description":"Traditional kopitiam since 1968.",
  "telephone":"+60 3-1234 5678",
  "servesCuisine":["Malaysian","Hainanese"],
  "image":{"@type":"ImageObject","url":"https://cdn.example/a.jpg"}}]}
</script></head><body></body></html>
"""

OG_ONLY_PAGE = """
<html><head><title>Roti Bakar</title>
<meta property="og:site_name" content="Roti Bakar Bakery">
<meta property="og:description" content="Sourdough and kaya toast.">
<meta property="og:image" content="https://cdn.example/roti.jpg">
</head><body></body></html>
"""


def extract(html: str, url: str = "https://ali.example/home"):
    return extractor.extract(make_page(html, url))


def test_prefers_structured_data_over_page_furniture():
    # A site that publishes JSON-LD has stated what it is; the title is a guess.
    assert extract(JSON_LD_PAGE).name == "Kedai Kopi Ali"


def test_finds_the_business_node_inside_a_graph():
    # CMS plugins routinely wrap everything in @graph with the WebSite first.
    assert extract(JSON_LD_PAGE).description == "Traditional kopitiam since 1968."


def test_reads_a_phone_number_from_structured_data():
    assert extract(JSON_LD_PAGE).phone == "+60 3-1234 5678"


def test_flattens_an_image_object_to_its_url():
    assert "https://cdn.example/a.jpg" in extract(JSON_LD_PAGE).photo_urls


def test_resolves_a_relative_image_against_the_landed_url():
    # A relative path is useless to a downstream renderer.
    assert "https://ali.example/img/shop.jpg" in extract(JSON_LD_PAGE).photo_urls


def test_merges_cuisine_and_keyword_descriptors():
    assert extract(JSON_LD_PAGE).descriptors == (
        "Malaysian",
        "Hainanese",
        "halal",
        "kopitiam",
    )


def test_falls_back_to_open_graph_when_there_is_no_structured_data():
    content = extract(OG_ONLY_PAGE)

    assert content.name == "Roti Bakar Bakery"
    assert content.description == "Sourdough and kaya toast."
    assert content.photo_urls == ("https://cdn.example/roti.jpg",)


def test_falls_back_to_the_title_when_nothing_else_names_the_business():
    content = extract("<html><head><title>  Kedai  Runcit </title></head></html>")

    assert content.name == "Kedai Runcit"


def test_reports_an_empty_page_as_empty():
    assert extract("<html><body><p>hello</p></body></html>").is_empty


def test_ignores_a_malformed_json_ld_block():
    # Broken blocks are common; one must not cost us the rest of the page.
    html = """
    <html><head><title>Fallback Name</title>
    <script type="application/ld+json">{not json,,}</script>
    </head></html>
    """

    assert extract(html).name == "Fallback Name"


def test_ignores_structured_data_that_is_not_about_a_business():
    html = """
    <html><head><title>Blog Post</title>
    <script type="application/ld+json">
    {"@type":"BlogPosting","name":"Ten Best Cafes"}</script>
    </head></html>
    """

    assert extract(html).name == "Blog Post"


def test_discards_an_image_that_does_not_resolve_to_http():
    html = """
    <html><head><script type="application/ld+json">
    {"@type":"Restaurant","name":"X","image":"data:image/png;base64,AAAA"}
    </script></head></html>
    """

    assert extract(html).photo_urls == ()


def test_accepts_a_type_written_as_a_full_schema_url():
    html = """
    <html><head><script type="application/ld+json">
    {"@type":"https://schema.org/Bakery","name":"Roti Bakar"}
    </script></head></html>
    """

    assert extract(html).name == "Roti Bakar"


def test_accepts_a_node_declaring_several_types():
    html = """
    <html><head><script type="application/ld+json">
    {"@type":["Thing","Restaurant"],"name":"Nasi Kandar"}
    </script></head></html>
    """

    assert extract(html).name == "Nasi Kandar"
