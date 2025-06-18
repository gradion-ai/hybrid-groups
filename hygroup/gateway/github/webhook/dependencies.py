import logging
from functools import lru_cache
from typing import Annotated, Awaitable, Callable

from fastapi import Depends

from hygroup.gateway.github.webhook.config import AppSettings

logger = logging.getLogger(__name__)


def settings_provider() -> AppSettings:  # type: ignore
    # set in application lifespan
    pass


SettingsDependency = Annotated[AppSettings, Depends(settings_provider)]


@lru_cache(maxsize=1)
def github_webhook_secret_provider(settings: SettingsDependency) -> bytes:  # type: ignore
    return settings.github_app_webhook_secret.encode("utf-8")


GithubWebhookSecretDependency = Annotated[bytes, Depends(github_webhook_secret_provider)]


def webhook_handler_provider(settings: SettingsDependency) -> Callable[[str, dict], Awaitable[None]]:  # type: ignore
    # set in application lifespan
    pass


WebhookHandlerDependency = Annotated[Callable[[str, dict], Awaitable[None]], Depends(webhook_handler_provider)]
