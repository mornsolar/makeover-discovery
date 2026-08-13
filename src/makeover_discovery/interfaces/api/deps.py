"""HTTP composition root.

Turns the object graph from ``makeover_discovery.composition`` into FastAPI
dependencies. Everything above depends on Protocols from
``application.ports``, so swapping an implementation means editing the
composition module and nothing else.

No DI framework: FastAPI's ``Depends`` plus structural typing already gives
constructor injection and per-request scoping. Adding a container would be
ceremony without benefit at this size.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichBusinessProfile,
)
from makeover_discovery.application.use_cases.generate_design_brief import GenerateDesignBrief
from makeover_discovery.composition import (
    SharedResources,
    build_discover_businesses,
    build_enrich_business_profile,
    build_generate_design_brief,
)
from makeover_discovery.config.settings import Settings, get_settings
from makeover_discovery.infrastructure.time.system_clock import SystemClock


def provide_clock() -> Clock:
    return SystemClock()


ClockDep = Annotated[Clock, Depends(provide_clock)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def provide_shared_resources(request: Request) -> SharedResources:
    """Fetch the process-wide resources placed on the app by the lifespan hook."""
    resources = getattr(request.app.state, "resources", None)
    if not isinstance(resources, SharedResources):
        raise RuntimeError("shared resources are unavailable; the app lifespan did not run")
    return resources


SharedResourcesDep = Annotated[SharedResources, Depends(provide_shared_resources)]


def provide_discover_businesses(
    settings: SettingsDep,
    resources: SharedResourcesDep,
    clock: ClockDep,
) -> DiscoverBusinesses:
    return build_discover_businesses(settings, resources, clock)


DiscoverBusinessesDep = Annotated[DiscoverBusinesses, Depends(provide_discover_businesses)]


def provide_enrich_business_profile(
    settings: SettingsDep,
    resources: SharedResourcesDep,
    clock: ClockDep,
) -> EnrichBusinessProfile:
    return build_enrich_business_profile(settings, resources, clock)


EnrichBusinessProfileDep = Annotated[
    EnrichBusinessProfile, Depends(provide_enrich_business_profile)
]


def provide_generate_design_brief(
    settings: SettingsDep,
    resources: SharedResourcesDep,
    clock: ClockDep,
) -> GenerateDesignBrief:
    return build_generate_design_brief(settings, resources, clock)


GenerateDesignBriefDep = Annotated[GenerateDesignBrief, Depends(provide_generate_design_brief)]
