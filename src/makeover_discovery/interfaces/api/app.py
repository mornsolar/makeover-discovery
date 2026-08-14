"""FastAPI application factory.

A factory rather than a module-level ``app`` so tests can build an isolated
instance and override dependencies without leaking state between cases.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from makeover_contracts.version import CONTRACT_VERSION

from makeover_discovery.composition import create_shared_resources
from makeover_discovery.config.settings import get_settings
from makeover_discovery.infrastructure.persistence.engine import init_db
from makeover_discovery.interfaces.api.errors import register_error_handlers
from makeover_discovery.interfaces.api.routers import brief, discover, enrich, health, projects


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own the HTTP client, cache, rate limiter, and DB engine for the
    process lifetime.

    These cannot be per-request: a rate limiter rebuilt for every call enforces
    nothing, and a connection pool rebuilt for every call is worse than none.
    """
    resources = create_shared_resources(get_settings())
    app.state.resources = resources
    await init_db(resources.db_engine)
    try:
        yield
    finally:
        await resources.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="makeover-discovery",
        version=CONTRACT_VERSION,
        summary="Postcode-driven business discovery and AI design briefs.",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(discover.router)
    app.include_router(enrich.router)
    app.include_router(brief.router)
    app.include_router(projects.router)
    return app


app = create_app()
