from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.evidence.schemas import MAX_EVIDENCE_REQUEST_BYTES

MAX_INCIDENT_MUTATION_BYTES = 32_768
MAX_AUTH_MUTATION_BYTES = 16_384
MAX_LAB_START_BYTES = 2_048

logger = logging.getLogger("otsoc.http")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _request_id(request: Request) -> str:
    candidate = request.headers.get("X-Request-ID", "")
    if _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


def _evidence_request_size_rejection(request: Request, request_id: str) -> Response | None:
    evidence_request = request.method == "POST" and request.url.path == "/api/v1/evidence"
    incident_mutation = (
        request.method in {"POST", "PATCH", "PUT"}
        and request.url.path.startswith("/api/v1/incidents/")
        and request.url.path.rsplit("/", maxsplit=1)[-1]
        in {"notes", "status", "assignment", "disposition", "report"}
    )
    auth_mutation = request.method in {"POST", "PATCH"} and (
        request.url.path == "/api/v1/auth/login"
        or request.url.path == "/api/v1/users"
        or request.url.path.startswith("/api/v1/users/")
    )
    lab_start = request.method == "POST" and request.url.path == "/api/v1/lab/start"
    if not evidence_request and not incident_mutation and not auth_mutation and not lab_start:
        return None
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        status_code, message = 411, "Content-Length is required."
    else:
        try:
            content_length = int(raw_length)
        except ValueError:
            status_code, message = 400, "Content-Length is invalid."
        else:
            if evidence_request:
                maximum = MAX_EVIDENCE_REQUEST_BYTES
            elif incident_mutation:
                maximum = MAX_INCIDENT_MUTATION_BYTES
            elif auth_mutation:
                maximum = MAX_AUTH_MUTATION_BYTES
            else:
                maximum = MAX_LAB_START_BYTES
            if 1 <= content_length <= maximum:
                return None
            status_code, message = 413, "Request body exceeds the size limit."
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": "request_size_error",
                "message": message,
                "request_id": request_id,
            }
        },
    )


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = _request_id(request)
    request.state.request_id = request_id
    started = time.perf_counter()
    response = _evidence_request_size_rejection(request, request_id)
    if response is None:
        response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), usb=(), serial=(), payment=()"
    )

    logger.info(
        "http_request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
