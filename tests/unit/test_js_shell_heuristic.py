"""Detecting a page that needs JavaScript to render."""

from __future__ import annotations

from makeover_discovery.infrastructure.crawl.js_shell_heuristic import (
    looks_like_js_shell,
    visible_text_of,
)
from tests.fakes.web import make_page

REACT_SHELL = """
<html><head><script src="/bundle.js"></script></head>
<body><div id="root"></div></body></html>
"""

SERVER_RENDERED = f"""
<html><body>
<h1>Kedai Kopi Ali</h1>
<p>{"Traditional kopitiam serving Hainanese coffee since 1968. " * 5}</p>
</body></html>
"""


def test_strips_scripts_and_style_out_of_visible_text():
    html = "<html><head><style>.x{color:red}</style></head><body>Hello</body></html>"

    assert visible_text_of(html) == "Hello"


def test_collapses_whitespace_across_tags():
    html = "<html><body>  Hello   <span> world </span>  </body></html>"

    assert visible_text_of(html) == "Hello world"


def test_flags_an_empty_spa_root_as_a_js_shell():
    assert looks_like_js_shell(make_page(REACT_SHELL))


def test_does_not_flag_a_server_rendered_page():
    assert not looks_like_js_shell(make_page(SERVER_RENDERED))


def test_flags_a_page_with_no_body_content_at_all():
    assert looks_like_js_shell(make_page("<html><head><title>Empty</title></head></html>"))
