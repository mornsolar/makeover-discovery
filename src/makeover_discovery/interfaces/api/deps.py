"""Composition root.

The only module that names concrete adapter classes. Everything above depends on
Protocols from ``application.ports``, so swapping an implementation means editing
this file and nothing else.

No DI framework: FastAPI's ``Depends`` plus structural typing already gives
constructor injection and per-request scoping. Adding a container would be
ceremony without benefit at this size.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.config.settings import Settings, get_settings
from makeover_discovery.infrastructure.time.system_clock import SystemClock


def provide_clock() -> Clock:
    return SystemClock()


ClockDep = Annotated[Clock, Depends(provide_clock)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
