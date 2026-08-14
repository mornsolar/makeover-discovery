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
from makeover_discovery.application.ports.project_repository import ProjectRepository
from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichBusinessProfile,
)
from makeover_discovery.application.use_cases.generate_design_brief import GenerateDesignBrief
from makeover_discovery.application.use_cases.publish_project import PublishProject
from makeover_discovery.application.use_cases.run_makeover_pipeline import RunMakeoverPipeline
from makeover_discovery.application.use_cases.save_project import SaveProject
from makeover_discovery.application.use_cases.takedown_project import TakedownProject
from makeover_discovery.application.use_cases.upload_before_image import UploadBeforeImage
from makeover_discovery.composition import (
    SharedResources,
    build_discover_businesses,
    build_enrich_business_profile,
    build_generate_design_brief,
    build_project_repository,
    build_publish_project,
    build_run_makeover_pipeline,
    build_save_project,
    build_takedown_project,
    build_upload_before_image,
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


def provide_run_makeover_pipeline(
    settings: SettingsDep,
    resources: SharedResourcesDep,
    clock: ClockDep,
) -> RunMakeoverPipeline:
    return build_run_makeover_pipeline(settings, resources, clock)


RunMakeoverPipelineDep = Annotated[RunMakeoverPipeline, Depends(provide_run_makeover_pipeline)]


def provide_save_project(
    settings: SettingsDep,
    resources: SharedResourcesDep,
    clock: ClockDep,
) -> SaveProject:
    return build_save_project(settings, resources, clock)


SaveProjectDep = Annotated[SaveProject, Depends(provide_save_project)]


def provide_project_repository(resources: SharedResourcesDep) -> ProjectRepository:
    return build_project_repository(resources)


ProjectRepositoryDep = Annotated[ProjectRepository, Depends(provide_project_repository)]


def provide_upload_before_image(
    settings: SettingsDep,
    resources: SharedResourcesDep,
) -> UploadBeforeImage:
    return build_upload_before_image(settings, resources)


UploadBeforeImageDep = Annotated[UploadBeforeImage, Depends(provide_upload_before_image)]


def provide_publish_project(resources: SharedResourcesDep) -> PublishProject:
    return build_publish_project(resources)


PublishProjectDep = Annotated[PublishProject, Depends(provide_publish_project)]


def provide_takedown_project(resources: SharedResourcesDep) -> TakedownProject:
    return build_takedown_project(resources)


TakedownProjectDep = Annotated[TakedownProject, Depends(provide_takedown_project)]
