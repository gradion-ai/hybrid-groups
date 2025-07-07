import logging
import re

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent.default.registry import DefaultAgentRegistry
from hygroup.gateway.slack.app_home.agent.handlers import AgentConfigHandlers
from hygroup.gateway.slack.app_home.secrets.handlers import SecretConfigHandlers
from hygroup.gateway.slack.app_home.views import HomeViewBuilder
from hygroup.user.default.registry import DefaultUserRegistry


class SlackHomeHandlers:
    """Handles Slack App Home interactions for user and system-wide configuration management.

    Args:
        client: Slack Web API client for making API calls
        app: Slack Bolt app instance for registering event handlers
        agent_registry: Registry containing available agents and their configurations
        system_editor_ids: List of Slack user IDs authorized to edit system-wide settings.
            If None, all users can edit system configurations.
    """

    def __init__(
        self,
        client: AsyncWebClient,
        app: AsyncApp,
        agent_registry: DefaultAgentRegistry,
        user_registry: DefaultUserRegistry,
        system_editor_ids: list[str] | None = None,
    ):
        self._client = client
        self._app = app
        self._system_editor_ids = system_editor_ids

        self._agent_config_handlers = AgentConfigHandlers(client, agent_registry)
        self._secret_config_handlers = SecretConfigHandlers(client, user_registry)

        self._logger = logging.getLogger(__name__)

    def register(self):
        # Home page handlers
        self._app.event("app_home_opened")(self.handle_app_home_opened)

        # Agent handlers
        self._app.action("home_add_agent")(
            self.require_system_edit_permission(self._agent_config_handlers.handle_add_agent),
        )
        self._app.view("home_agent_added_view")(
            self.refresh_home_after_completion(
                self.require_system_edit_permission(self._agent_config_handlers.handle_agent_added)
            )
        )
        self._app.action(re.compile(r"^home_agent_menu:"))(
            self.require_system_edit_permission_for_agent_menu(self._agent_config_handlers.handle_agent_menu)
        )
        self._app.view("home_agent_edited_view")(
            self.refresh_home_after_completion(
                self.require_system_edit_permission(self._agent_config_handlers.handle_agent_edited)
            )
        )
        self._app.view("home_agent_delete_confirm_view")(
            self.refresh_home_after_completion(
                self.require_system_edit_permission(self._agent_config_handlers.handle_agent_delete_confirmed)
            )
        )

        # User secret handlers
        self._app.action("home_add_user_secret")(self._secret_config_handlers.handle_add_user_secret)
        self._app.view("home_user_secret_added_view")(
            self.refresh_home_after_completion(self._secret_config_handlers.handle_user_secret_added)
        )
        self._app.action(re.compile(r"^home_user_secret_var_menu:"))(
            self._secret_config_handlers.handle_user_secret_menu
        )
        self._app.view("home_user_secret_edited_view")(
            self.refresh_home_after_completion(self._secret_config_handlers.handle_user_secret_edited)
        )
        self._app.view("home_user_secret_delete_confirm_view")(
            self.refresh_home_after_completion(self._secret_config_handlers.handle_user_secret_delete_confirmed)
        )

        self._logger.info("All handlers registered")

    async def handle_app_home_opened(self, client, event, logger):
        try:
            user_id = event["user"]
            await self.refresh_home_view(user_id)
        except Exception as e:
            self._logger.error(f"Error handling app home opened: {e}")

    async def refresh_home_view(self, user_id: str):
        try:
            username = await self._get_user_display_name(user_id)
            agents = await self._agent_config_handlers._get_agents()
            user_secrets = await self._secret_config_handlers.get_user_secrets(user_id)
            is_system_editor = self._is_system_editor(user_id)

            view = HomeViewBuilder.build_home_view(
                username=username,
                user_secrets=user_secrets,
                agents=agents,
                is_system_editor=is_system_editor,
            )

            await self._client.views_publish(user_id=user_id, view=view)
        except Exception as e:
            self._logger.error(f"Error refreshing home view for {user_id}: {e}")

    def _is_system_editor(self, user_id: str) -> bool:
        if self._system_editor_ids is None:
            return True
        return user_id in self._system_editor_ids

    async def _get_user_display_name(self, user_id: str) -> str:
        try:
            response = await self._client.users_info(user=user_id)
            user_info = response["user"]
            return user_info.get("display_name") or user_info.get("real_name") or user_info.get("name", "User")
        except Exception as e:
            self._logger.error(f"Error fetching user info for {user_id}: {e}")
            return "User"

    def require_system_edit_permission(self, handler):
        async def wrapper(ack, body, client, *args, **kwargs):
            user_id = body["user"]["id"]
            if not self._is_system_editor(user_id):
                await ack()
                self._logger.warning(f"User {user_id} attempted to edit system config without permission")
                return
            return await handler(ack, body, client, *args, **kwargs)

        return wrapper

    def refresh_home_after_completion(self, handler):
        async def wrapper(ack, body, client, view, logger, *args, **kwargs):
            result = await handler(ack, body, client, view, logger, *args, **kwargs)
            await self.refresh_home_view(body["user"]["id"])
            return result

        return wrapper

    def require_system_edit_permission_for_agent_menu(self, handler):
        async def wrapper(ack, body, client, *args, **kwargs):
            user_id = body["user"]["id"]
            selected_option = body["actions"][0]["selected_option"]["value"]
            action, _ = selected_option.split(":", 1)

            if action in ["edit", "delete"]:
                if not self._is_system_editor(user_id):
                    await ack()
                    self._logger.warning(f"User {user_id} attempted to edit system config without permission: {action}")
                    return

            result = await handler(ack, body, client, *args, **kwargs)

            if action in ["edit", "delete"]:
                await self.refresh_home_view(user_id)

            return result

        return wrapper
