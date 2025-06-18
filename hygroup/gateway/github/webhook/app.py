import logging
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import APIRouter, FastAPI

from hygroup.gateway.github.webhook import api as hooks_api
from hygroup.gateway.github.webhook import dependencies as deps
from hygroup.gateway.github.webhook.config import AppSettings

logger = logging.getLogger(__name__)


def create_app(
    settings: AppSettings,
    event_handler: Callable[[str, dict], Awaitable[None]] | None = None,
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
    api_router.include_router(hooks_api.router, tags=["hooks"])

    app = FastAPI(
        lifespan=lifespan,
        title="Github Gateway",
        description="Github Gateway",
        version="0.0.1",
        summary="Github Gateway",
    )
    app.include_router(api_router, prefix="/api/v1")

    app.dependency_overrides[deps.settings_provider] = lambda: settings
    app.dependency_overrides[deps.webhook_handler_provider] = lambda: event_handler
    return app


def setup_logging(settings: AppSettings):
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
