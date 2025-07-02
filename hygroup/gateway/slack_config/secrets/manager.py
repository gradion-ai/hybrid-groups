import logging
import re
from typing import Dict

from slack_sdk.web.async_client import AsyncWebClient

from hygroup.gateway.slack_config.models import ValidationError
from hygroup.gateway.slack_config.secrets.views import SecretViewBuilder
from hygroup.gateway.slack_config.stores import SecretStore

logger = logging.getLogger(__name__)


class SecretConfigManager:
    def __init__(self, client: AsyncWebClient, store: SecretStore):
        self._client = client
        self._store = store

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

    async def handle_add_user_secret(self, ack, body, client):
        logger.debug("Handle add user secret")
        await ack()

        modal = SecretViewBuilder.build_add_secret_modal(is_global=False)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_user_secret_added(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        key = view["state"]["values"]["env_key"]["key_input"]["value"]
        value = view["state"]["values"]["env_value"]["value_input"]["value"]

        # Validate key
        if error := self._validate_key(key):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "env_key": error.message,
                    },
                }
            )
            return

        # Validate value
        if error := self._validate_value(value):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "env_value": error.message,
                    },
                }
            )
            return

        key = key.upper()
        await self._store.set_user_secret(user_id, key, value)
        await ack()

        # Refresh handled by home manager
        logger.info(f"User secret added for {user_id}: {key}")

    async def handle_user_secret_menu(self, ack, body, client):
        logger.debug("Handle user secret menu")
        await ack()

        user_id = body["user"]["id"]
        selected_option = body["actions"][0]["selected_option"]["value"]
        action, key = selected_option.split(":", 1)

        if action == "edit":
            await self._handle_edit_user_secret(body, key)
        elif action == "delete":
            await self._handle_delete_user_secret(body, user_id, key)

    async def _handle_edit_user_secret(self, body, key: str):
        modal = SecretViewBuilder.build_edit_secret_modal(key, is_global=False)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def _handle_delete_user_secret(self, body, user_id: str, key: str):
        modal = SecretViewBuilder.build_delete_secret_modal(key, user_id, is_global=False)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_user_secret_edited(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        key = view["private_metadata"]
        value = view["state"]["values"]["env_value"]["value_input"]["value"]

        # Validate value
        if error := self._validate_value(value):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "env_value": error.message,
                    },
                }
            )
            return

        await self._store.set_user_secret(user_id, key, value)
        await ack()

        logger.info(f"User secret edited for {user_id}: {key}")

    async def handle_user_secret_delete_confirmed(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        metadata = view["private_metadata"]
        stored_user_id, key = metadata.split(":", 1)

        # Security check
        if user_id == stored_user_id:
            await self._store.delete_user_secret(user_id, key)
            logger.info(f"User secret deleted for {user_id}: {key}")

        await ack()

    async def handle_add_global_secret(self, ack, body, client):
        await ack()

        # Admin check should be done by caller
        modal = SecretViewBuilder.build_add_secret_modal(is_global=True)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_global_secret_added(self, ack, body, client, view, slack_logger):
        key = view["state"]["values"]["global_secret_key"]["key_input"]["value"]
        value = view["state"]["values"]["global_secret_value"]["value_input"]["value"]

        # Validate key
        if error := self._validate_key(key):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "global_secret_key": error.message,
                    },
                }
            )
            return

        # Validate value
        if error := self._validate_value(value):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "global_secret_value": error.message,
                    },
                }
            )
            return

        key = key.upper()
        await self._store.set_global_secret(key, value)
        await ack()

        logger.info(f"Global secret added: {key}")

    async def handle_global_secret_menu(self, ack, body, client):
        await ack()

        user_id = body["user"]["id"]
        selected_option = body["actions"][0]["selected_option"]["value"]
        action, key = selected_option.split(":", 1)

        if action == "edit":
            await self._handle_edit_global_secret(body, key)
        elif action == "delete":
            await self._handle_delete_global_secret(body, user_id, key)

    async def _handle_edit_global_secret(self, body, key: str):
        modal = SecretViewBuilder.build_edit_secret_modal(key, is_global=True)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def _handle_delete_global_secret(self, body, user_id: str, key: str):
        modal = SecretViewBuilder.build_delete_secret_modal(key, user_id, is_global=True)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_global_secret_edited(self, ack, body, client, view, slack_logger):
        key = view["private_metadata"]
        value = view["state"]["values"]["global_secret_value"]["value_input"]["value"]

        # Validate value
        if error := self._validate_value(value):
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "global_secret_value": error.message,
                    },
                }
            )
            return

        await self._store.set_global_secret(key, value)
        await ack()

        logger.info(f"Global secret edited: {key}")

    async def handle_global_secret_delete_confirmed(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        metadata = view["private_metadata"]
        stored_user_id, key = metadata.split(":", 1)

        # Security check
        if user_id == stored_user_id:
            await self._store.delete_global_secret(key)
            logger.info(f"Global secret deleted: {key}")

        await ack()

    async def get_user_secrets(self, user_id: str) -> Dict[str, str]:
        return await self._store.get_user_secrets(user_id)

    async def get_global_secrets(self) -> Dict[str, str]:
        return await self._store.get_global_secrets()
