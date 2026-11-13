"""
The Invisible Healer
Global Exception Handling

Responsibilities:
    - Handle custom application exceptions.
    - Handle FastAPI HTTP exceptions.
    - Handle request validation failures.
    - Handle unexpected server exceptions.
    - Return consistent API error structures.
    - Avoid exposing internal application details.

Phase:
    01 - Project Skeleton
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """
    Base exception for expected application errors.

    Services and domain modules can later raise
    subclasses of this exception.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "APPLICATION_ERROR",
    ) -> None:

        self.message = message
        self.status_code = status_code
        self.error_code = error_code

        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all global exception handlers.
    Called once during application construction.
    """

    # -----------------------------------------
    # Custom application exceptions
    # -----------------------------------------

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                },
            },
        )

    # -----------------------------------------
    # HTTP exceptions, including 404 and 405
    # -----------------------------------------

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                },
            },
            headers=exc.headers,
        )

    # -----------------------------------------
    # Request validation exceptions
    # -----------------------------------------

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []

        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": errors,
                },
            },
        )

    # -----------------------------------------
    # Unhandled exceptions
    # -----------------------------------------

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception at %s",
            request.url.path,
            exc_info=(
                type(exc),
                exc,
                exc.__traceback__,
            ),
        )

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": ("An unexpected server error occurred."),
                },
            },
        )
