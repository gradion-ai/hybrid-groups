import logging
from typing import Optional

from slack_sdk.web.async_client import AsyncWebClient

from hygroup.gateway.slack_config.models import UserPreferencesViewModel
from hygroup.gateway.slack_config.preferences.views import UserPreferenceViewBuilder
from hygroup.gateway.slack_config.stores import UserPreferencesStore

logger = logging.getLogger(__name__)


class UserPreferenceConfigManager:
    def __init__(self, client: AsyncWebClient, store: UserPreferencesStore):
        self._client = client
        self._store = store

    async def get_preferences(self, user_id: str) -> Optional[UserPreferencesViewModel]:
        return await self._store.get(user_id)

    async def has_preferences(self, user_id: str) -> bool:
        return await self._store.has_preferences(user_id)

    async def handle_user_preferences_overflow(self, ack, body, client):
        logger.debug("Handle user preferences overflow")
        await ack()

        user_id = body["user"]["id"]
        selected_option = body["actions"][0]["selected_option"]["value"]

        if selected_option == "config_view_user_preferences":
            await self._handle_view_user_preferences_internal(body, user_id)
        elif selected_option == "config_edit_user_preferences":
            await self._handle_edit_user_preferences_internal(body, user_id)

    async def handle_user_preferences_create(self, ack, body, client):
        logger.debug("Handle user preferences create")
        await ack()

        user_id = body["user"]["id"]
        await self._handle_edit_user_preferences_internal(body, user_id)

    async def _handle_view_user_preferences_internal(self, body, user_id: str):
        logger.debug(f"Handle view user preferences for user {user_id}")

        current_preferences = await self._store.get(user_id)

        modal = UserPreferenceViewBuilder.build_user_preferences_view_modal(current_preferences)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def _handle_edit_user_preferences_internal(self, body, user_id: str):
        logger.debug(f"Handle edit user preferences for user {user_id}")

        current_preferences = await self._store.get(user_id)

        modal = UserPreferenceViewBuilder.build_user_preferences_edit_modal(current_preferences)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_user_preferences_edited(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        content = view["state"]["values"]["preferences_content"]["content_input"]["value"]

        # Allow empty content (user can clear their preferences)
        if content is None:
            content = ""

        try:
            await self._store.set(user_id, content.strip())
            await ack()
            logger.info(f"User preferences updated successfully for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating user preferences for user {user_id}: {e}")
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "preferences_content": "Failed to update preferences. Please try again.",
                    },
                }
            )
