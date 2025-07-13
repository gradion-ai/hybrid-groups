import logging
from typing import Callable

from slack_sdk.web.async_client import AsyncWebClient

from hygroup.gateway.slack.app_home.preferences.views import UserPreferenceViewBuilder
from hygroup.user.default.preferences import DefaultPreferenceStore

logger = logging.getLogger(__name__)


class UserPreferenceConfigHandlers:
    def __init__(
        self,
        client: AsyncWebClient,
        preference_store: DefaultPreferenceStore,
        resolve_system_user_id: Callable[[str], str],
    ):
        self._client = client
        self._preference_store = preference_store
        self._resolve_system_user_id = resolve_system_user_id

    async def has_user_preferences(self, slack_user_id: str) -> bool:
        system_user_id = self._resolve_system_user_id(slack_user_id)
        return await self._get_user_preferences(system_user_id) is not None

    async def _get_user_preferences(self, slack_user_id: str) -> str | None:
        system_user_id = self._resolve_system_user_id(slack_user_id)
        return await self._preference_store.get_preferences(system_user_id)

    async def _set_user_preferences(self, slack_user_id: str, preferences: str):
        system_user_id = self._resolve_system_user_id(slack_user_id)
        await self._preference_store.set_preferences(system_user_id, preferences)

    async def _delete_user_preferences(self, slack_user_id: str):
        system_user_id = self._resolve_system_user_id(slack_user_id)
        await self._preference_store.delete_preferences(system_user_id)

    async def handle_user_preferences_overflow(self, ack, body, client):
        await ack()

        user_id = body["user"]["id"]
        selected_option = body["actions"][0]["selected_option"]["value"]

        if selected_option == "home_edit_user_preferences":
            await self._handle_edit_user_preferences_internal(body, user_id)
        elif selected_option == "home_delete_user_preferences":
            await self._handle_delete_user_preferences_internal(body, user_id)

    async def handle_user_preferences_create(self, ack, body, client):
        await ack()

        user_id = body["user"]["id"]
        await self._handle_edit_user_preferences_internal(body, user_id)

    async def _handle_edit_user_preferences_internal(self, body, user_id: str):
        preferences = await self._get_user_preferences(user_id)
        modal = UserPreferenceViewBuilder.build_user_preferences_edit_modal(preferences)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def _handle_delete_user_preferences_internal(self, body, user_id: str):
        modal = UserPreferenceViewBuilder.build_user_preferences_delete_modal()
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_user_preferences_edited(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]
        content = view["state"]["values"]["preferences_content"]["content_input"]["value"]

        if content is None:
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "preferences_content": "User preferences cannot be empty",
                    },
                }
            )
            return

        try:
            await self._set_user_preferences(user_id, content.strip())
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

    async def handle_user_preferences_delete_confirmed(self, ack, body, client, view, slack_logger):
        user_id = body["user"]["id"]

        try:
            await self._delete_user_preferences(user_id)
            await ack()
            logger.info(f"User preferences deleted successfully for user {user_id}")
        except Exception as e:
            logger.error(f"Error deleting user preferences for user {user_id}: {e}")
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "general": "Failed to delete preferences. Please try again.",
                    },
                }
            )
