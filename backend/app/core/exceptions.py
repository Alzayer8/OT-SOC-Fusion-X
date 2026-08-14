from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("otsoc.errors")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unavailable")


def _error_body(code: str, message: str, request_id: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            code = "not_found"
            message = "The requested resource was not found."
        else:
            code = "http_error"
            message = str(exc.detail) if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, message, _request_id(request)),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        safe_details = [
            {
                "location": [str(part) for part in error["loc"]],
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "validation_error",
                "The request did not pass validation.",
                _request_id(request),
                safe_details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def fastapi_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return await http_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            extra={"request_id": _request_id(request), "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "internal_error",
                "The service could not complete the request.",
                _request_id(request),
            ),
        )
