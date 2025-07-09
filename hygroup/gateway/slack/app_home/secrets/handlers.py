import logging
import re
from typing import Callable

from slack_sdk.web.async_client import AsyncWebClient

from hygroup.gateway.slack.app_home.models import ValidationError
from hygroup.gateway.slack.app_home.secrets.views import SecretViewBuilder
from hygroup.user.base import User
from hygroup.user.default.registry import DefaultUserRegistry

logger = logging.getLogger(__name__)


class SecretConfigHandlers:
    def __init__(
        self,
        client: AsyncWebClient,
        user_registry: DefaultUserRegistry,
        resolve_system_user_id: Callable[[str], str],
    ):
        self._client = client
        self._user_registry = user_registry
        self._resolve_system_user_id = resolve_system_user_id

    @staticmethod
    def _validate_key(key: str) -> ValidationError | None:
        if not key or not key.strip():
            return ValidationError(field="key", message="Secret name is required")

        if not re.match(r"^[A-Z][A-Z0-9_]*$", key.upper()):
            return ValidationError(
                field="key",
                message="Secret name must start with a letter and contain only letters, numbers, and underscores",
            )

        return None

    @staticmethod
    def _validate_value(value: str) -> ValidationError | None:
        if not value:
            return ValidationError(field="value", message="Secret value is required")
        return None

    async def get_user_secrets(self, slack_user_id: str) -> dict[str, str]:
        system_user_id = self._resolve_system_user_id(slack_user_id)

        if secrets := self._user_registry.get_secrets(system_user_id):
            return {k.upper(): v for k, v in secrets.items() if k.upper() != "PASSWORD_HASH"}

        return {}

    async def _add_user_secret(self, slack_user_id: str, key: str, value: str):
        system_user_id = self._resolve_system_user_id(slack_user_id)
        _key = key.upper()

        secrets = self._user_registry.get_secrets(system_user_id) or {}
        if any(k.upper() == _key for k in secrets.keys()):
            raise ValueError(f"Secret '{_key}' already exists.")

        if not secrets and self._user_registry.get_user(system_user_id) is None:
            await self._user_registry.register(User(system_user_id))

        await self._user_registry.set_secret(system_user_id, _key, value)

    async def _edit_user_secret(self, slack_user_id: str, key: str, value: str):
        system_user_id = self._resolve_system_user_id(slack_user_id)
        await self._user_registry.set_secret(system_user_id, key.upper(), value)

    async def _delete_user_secret(self, slack_user_id: str, key: str):
        system_user_id = self._resolve_system_user_id(slack_user_id)
        await self._user_registry.delete_secret(system_user_id, key.upper())

    async def handle_add_user_secret(self, ack, body, client):
        await ack()
        modal = SecretViewBuilder.build_add_secret_modal()
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_user_secret_added(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        key = view["state"]["values"]["user_secret_key"]["key_input"]["value"]
        value = view["state"]["values"]["user_secret_value"]["value_input"]["value"]

        if error := self._validate_key(key):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "user_secret_key": error.message,
                    },
                }
            )
            return

        if error := self._validate_value(value):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "user_secret_value": error.message,
                    },
                }
            )
            return

        try:
            await self._add_user_secret(user_id, key, value)
        except ValueError as e:
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "user_secret_key": str(e),
                    },
                }
            )
            return

        await ack()

        logger.info(f"User secret added for {user_id}: {key}")

    async def handle_user_secret_menu(self, ack, body, client):
        await ack()

        user_id = body["user"]["id"]
        selected_option = body["actions"][0]["selected_option"]["value"]
        action, key = selected_option.split(":", 1)

        if action == "edit":
            await self._handle_edit_user_secret(body, key)
        elif action == "delete":
            await self._handle_delete_user_secret(body, user_id, key)

    async def _handle_edit_user_secret(self, body, key: str):
        modal = SecretViewBuilder.build_edit_secret_modal(key)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def _handle_delete_user_secret(self, body, user_id: str, key: str):
        modal = SecretViewBuilder.build_delete_secret_modal(key, user_id)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_user_secret_edited(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        key = view["private_metadata"]
        value = view["state"]["values"]["user_secret_value"]["value_input"]["value"]

        if error := self._validate_value(value):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "user_secret_value": error.message,
                    },
                }
            )
            return

        await self._edit_user_secret(user_id, key, value)
        await ack()

        logger.info(f"User secret edited for {user_id}: {key}")

    async def handle_user_secret_delete_confirmed(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        metadata = view["private_metadata"]
        stored_user_id, key = metadata.split(":", 1)

        if user_id == stored_user_id:
            await self._delete_user_secret(user_id, key)
            logger.info(f"User secret deleted for {user_id}: {key}")

        await ack()
