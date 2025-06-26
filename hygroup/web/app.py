import logging
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hygroup.user.base import UserRegistry
from hygroup.web import dependencies as deps
from hygroup.web.auth import api as auth_api
from hygroup.web.config import AppSettings
from hygroup.web.health import api as health_api
from hygroup.web.users import api as users_api

logger = logging.getLogger(__name__)


def create_app(
    settings: AppSettings,
    user_registry: UserRegistry,
    shutdown_handler: Callable[[], Awaitable[None]] | None = None,
):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            logger.info("Starting application")
            yield
        finally:
            if shutdown_handler:
                logger.info("Invoking shutdown handler")
                await shutdown_handler()
            logger.info("Application shutdown completed")

    setup_logging(settings)

    api_router = APIRouter()
    api_router.include_router(auth_api.router, prefix="/auth", tags=["auth"])
    api_router.include_router(health_api.router, tags=["health"])
    api_router.include_router(users_api.router, prefix="/users", tags=["users"])

    app = FastAPI(
        lifespan=lifespan,
        title="Hybrid Groups Backend",
        description="Hybrid Groups Backend",
        version="0.0.1",
        summary="Hybrid Groups Backend",
    )
    app.include_router(api_router, prefix="/api/v1")

    app.dependency_overrides[deps.settings_provider] = lambda: settings
    app.dependency_overrides[deps.user_registry_provider] = lambda: user_registry

    # Add CORS middleware to allow requests from the frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["*"],
    )

    return app


def setup_logging(settings: AppSettings):
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
