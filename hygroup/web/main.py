import asyncio
import logging

import uvicorn
from dotenv import load_dotenv

from hygroup.user.default.registry import DefaultUserRegistry
from hygroup.web.app import create_app
from hygroup.web.config import AppSettings

logger = logging.getLogger(__name__)


async def main(settings: AppSettings):
    try:
        user_registry = DefaultUserRegistry(
            registry_path=settings.user_registry_path,
        )

        async def shutdown_handler():
            logger.info("Shutdown completed")

        app = create_app(
            settings,
            user_registry,
            shutdown_handler,
        )

        app_config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=settings.api_port,
            log_config=str(settings.log_config_path),
            log_level=settings.log_level.lower(),
            reload=False,
        )

        app_server = uvicorn.Server(app_config)

        await app_server.serve()
    finally:
        logger.info("FastAPI server stopped")


if __name__ == "__main__":
    load_dotenv()
    settings = AppSettings()

    asyncio.run(main(settings))
