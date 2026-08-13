"""Duck-typed fakes for the Playwright surfaces ``PlaywrightWebFetcher`` uses.

Real Chromium is not part of this toolchain's automated setup (see the
README), so these stand in for ``Browser``/``BrowserContext``/``Page``/
``Response`` without needing the binary. They only implement what the adapter
actually calls, and they are not typed against playwright's own types: the
adapter is what mypy checks, and it depends on those types, not these fakes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

_UNSET: Final = object()
"""Distinguishes "use the default response" from an explicit ``response=None``,
which a test uses to simulate Playwright reporting no navigation response."""


class FakeResponse:
    def __init__(self, *, ok: bool = True, status: int = 200) -> None:
        self.ok = ok
        self.status = status


class FakePage:
    def __init__(
        self,
        *,
        html: str = "<html><body>rendered</body></html>",
        url: str = "https://ali.example/menu",
        response: FakeResponse | object | None = _UNSET,
        goto_error: Exception | None = None,
    ) -> None:
        self._html = html
        self.url = url
        self._response: FakeResponse | None = (
            FakeResponse() if response is _UNSET else response  # type: ignore[assignment]
        )
        self._goto_error = goto_error
        self.goto_calls: list[tuple[str, dict[str, object]]] = []

    async def goto(self, url: str, **kwargs: object) -> FakeResponse | None:
        self.goto_calls.append((url, kwargs))
        if self._goto_error is not None:
            raise self._goto_error
        return self._response

    async def content(self) -> str:
        return self._html


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self._page = page
        self.closed = False

    async def new_page(self) -> FakePage:
        return self._page

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self._page = page
        self.contexts: list[FakeContext] = []
        self.user_agents: list[str] = []

    async def new_context(self, *, user_agent: str) -> FakeContext:
        self.user_agents.append(user_agent)
        context = FakeContext(self._page)
        self.contexts.append(context)
        return context


def launcher_for(page: FakePage) -> tuple[object, FakeBrowser]:
    """A ``BrowserLauncher`` yielding a fresh ``FakeBrowser`` wrapping ``page``."""
    browser = FakeBrowser(page)

    @asynccontextmanager
    async def launch() -> AsyncIterator[FakeBrowser]:
        yield browser

    return launch, browser
