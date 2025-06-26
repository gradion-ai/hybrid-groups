import logging
from typing import Annotated

from fastapi import Depends

from hygroup.user.base import UserRegistry
from hygroup.web.config import AppSettings

logger = logging.getLogger(__name__)


def settings_provider() -> AppSettings:  # type: ignore
    # set in application lifespan
    pass


SettingsDependency = Annotated[AppSettings, Depends(settings_provider)]


def user_registry_provider() -> UserRegistry:  # type: ignore
    # set in application lifespan
    pass


UserRegistryDependency = Annotated[UserRegistry, Depends(user_registry_provider)]
