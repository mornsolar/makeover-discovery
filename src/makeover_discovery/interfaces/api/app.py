"""FastAPI application factory.

A factory rather than a module-level ``app`` so tests can build an isolated
instance and override dependencies without leaking state between cases.
"""

from __future__ import annotations

from fastapi import FastAPI
from makeover_contracts.version import CONTRACT_VERSION

from makeover_discovery.interfaces.api.routers import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="makeover-discovery",
        version=CONTRACT_VERSION,
        summary="Postcode-driven business discovery and AI design briefs.",
    )
    app.include_router(health.router)
    return app


app = create_app()
