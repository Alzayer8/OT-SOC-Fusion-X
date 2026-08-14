from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.evidence import router as evidence_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.lab import router as lab_router
from app.api.meta import router as meta_router
from app.api.product import router as product_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import request_context_middleware
from app.db.session import session_scope
from app.lab.service import startup_baseline


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if (
            active_settings.app_env == "development"
            and active_settings.scenario_lab_startup_enabled
        ):
            with session_scope(active_settings) as session:
                startup_baseline(active_settings, session)
        yield

    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        description=(
            "Repository and contract foundation for the isolated, advisory-only "
            "OT-SOC Fusion X academic prototype."
        ),
        lifespan=lifespan,
    )
    application.state.settings = active_settings
    application.dependency_overrides[get_settings] = lambda: active_settings

    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origin_strings,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "X-Request-ID",
            "X-CSRF-Token",
        ],
    )
    application.middleware("http")(request_context_middleware)
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(meta_router)
    application.include_router(evidence_router)
    application.include_router(incidents_router)
    application.include_router(product_router)
    application.include_router(lab_router)
    return application


app = create_app()
