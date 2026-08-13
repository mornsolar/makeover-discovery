"""Liveness endpoint.

Reports the contract version so a misdeployed pair of services is visible from
outside without reading logs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from makeover_contracts.version import CONTRACT_VERSION
from pydantic import BaseModel

from makeover_discovery.interfaces.api.deps import ClockDep, SettingsDep

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str
    contract_version: str
    checked_at: datetime


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(clock: ClockDep, settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        environment=settings.environment,
        contract_version=CONTRACT_VERSION,
        checked_at=clock.now(),
    )
