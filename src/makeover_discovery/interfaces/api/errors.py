"""Translation of domain errors into HTTP responses.

The domain raises errors in its own vocabulary and knows nothing about status
codes; mapping them is an interface concern, so it happens exactly here. A
domain error that reaches the client as an unhandled 500 is a bug in this table,
not in the caller.
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from makeover_discovery.domain.errors import (
    MakeoverError,
    NotFoundError,
    PolicyViolationError,
    UpstreamError,
    ValidationError,
)

STATUS_BY_ERROR: Final[dict[type[MakeoverError], int]] = {
    ValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    PolicyViolationError: status.HTTP_403_FORBIDDEN,
    UpstreamError: status.HTTP_502_BAD_GATEWAY,
}
DEFAULT_STATUS: Final = status.HTTP_500_INTERNAL_SERVER_ERROR


def status_for(error: MakeoverError) -> int:
    """Most specific mapped status for ``error``'s type."""
    for error_type in type(error).__mro__:
        if error_type in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[error_type]
    return DEFAULT_STATUS


async def handle_makeover_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, MakeoverError):  # pragma: no cover - registered by type
        raise exc
    return JSONResponse(
        status_code=status_for(exc),
        content={"error": type(exc).__name__, "detail": str(exc)},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(MakeoverError, handle_makeover_error)
