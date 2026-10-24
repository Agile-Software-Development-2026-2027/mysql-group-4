import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AccessDeniedError, InvalidMissionPeriodError, InvalidMissionStateError,
    ResourceNotFoundError,
)
from app.schemas.service_error import ServiceError

logger = logging.getLogger(__name__)


def _error_response(request: Request, status_code: int, message: str) -> JSONResponse:
    error = ServiceError(timestamp=datetime.now(timezone.utc),
                         url=request.url.path, message=message)
    return JSONResponse(status_code=status_code, content=error.model_dump(mode="json"))


async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    return _error_response(request, 404, str(exc))


async def access_denied_handler(request: Request, exc: AccessDeniedError) -> JSONResponse:
    return _error_response(request, 403, str(exc))


async def invalid_mission_handler(request: Request, exc: ValueError) -> JSONResponse:
    return _error_response(request, 400, str(exc))


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error for %s", request.url.path,
                 exc_info=(type(exc), exc, exc.__traceback__))
    return _error_response(request, 500, "Internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
    app.add_exception_handler(AccessDeniedError, access_denied_handler)
    app.add_exception_handler(InvalidMissionPeriodError, invalid_mission_handler)
    app.add_exception_handler(InvalidMissionStateError, invalid_mission_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
