import logging
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hygroup.api import dependencies as deps
from hygroup.api.auth.routes import router as auth_router
from hygroup.api.config import ApiServerSettings
from hygroup.api.health.routes import router as health_router
from hygroup.api.users.routes import router as users_router
from hygroup.user.base import UserRegistry

logger = logging.getLogger(__name__)


def create_app(
    settings: ApiServerSettings,
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
    api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
    api_router.include_router(health_router, tags=["health"])
    api_router.include_router(users_router, prefix="/users", tags=["users"])

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

    # Add CORS middleware to allow requests from the Web UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["*"],
    )

    return app


def setup_logging(settings: ApiServerSettings):
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
