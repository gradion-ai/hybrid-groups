import logging
from typing import Annotated

from fastapi import Depends

from hygroup.api.config import ApiServerSettings
from hygroup.user.base import UserRegistry

logger = logging.getLogger(__name__)


def settings_provider() -> ApiServerSettings:  # type: ignore
    # set in application lifespan
    pass


SettingsDependency = Annotated[ApiServerSettings, Depends(settings_provider)]


def user_registry_provider() -> UserRegistry:  # type: ignore
    # set in application lifespan
    pass


UserRegistryDependency = Annotated[UserRegistry, Depends(user_registry_provider)]
