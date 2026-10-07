from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import logging

from app.api.routes import api_router
from app.core.config import ProductionConfigError, get_settings, validate_settings
from app.core.database import Base, engine
from app.core.errors import RequestContextMiddleware, register_exception_handlers
from app.core.logging import setup_logging
import app.models  # noqa: F401
import app.core.org_flush  # noqa: F401 — tenant org_id flush hook

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    try:
        validate_settings(settings)
    except ProductionConfigError as exc:
        logger.error("Production configuration invalid: %s", exc)
        raise
    # Skip DB bootstrap in automated tests (suite uses in-memory SQLite overrides).
    if (settings.app_env or "").strip().lower() != "test":
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Database bootstrap skipped: %s", exc)
    yield


def custom_openapi(app: FastAPI):
    if app.openapi_schema: 
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=[
            {"name": "System", "description": "Health, providers, readiness"},
            {"name": "Leads", "description": "Lead CRUD and pipeline"},
            {"name": "Discovery", "description": "Lead generation / Google Places"},
            {"name": "Website", "description": "Website intelligence"},
            {"name": "Contacts", "description": "Email discovery"},
            {"name": "Verification", "description": "Email verification"},
            {"name": "AI", "description": "Qualification"},
            {"name": "Outreach", "description": "Draft generation and approval"},
            {"name": "Email", "description": "Sending and webhooks"},
            {"name": "Campaigns", "description": "Campaigns and follow-ups"},
            {"name": "Replies", "description": "Reply intelligence"},
            {"name": "Meetings", "description": "Booking and calendar"},
            {"name": "Pipeline", "description": "CRM pipeline"},
        ],
    )
    app.openapi_schema = schema
    return app.openapi_schema


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()

    app = FastAPI(
        title="LeadFlow AI API",
        description=(
            "LeadFlow AI — lead discovery through meeting automation & CRM. "
            "Providers are pluggable; secrets never appear in API responses."
        ),
        version="0.15.0",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.openapi = lambda: custom_openapi(app)  # type: ignore[method-assign]
    return app


app = create_app()
