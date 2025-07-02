import logging
import re

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent.default.registry import DefaultAgentRegistry
from hygroup.gateway.slack.config.agent.manager import AgentConfigManager
from hygroup.gateway.slack.config.home.views import HomeViewBuilder


class SlackHomeManager:
    def __init__(self, client: AsyncWebClient, app: AsyncApp, agent_registry: DefaultAgentRegistry):
        self._client = client
        self._app = app
        self._admin_cache: dict[str, bool] = {}

        self._agent_config_manager = AgentConfigManager(client, agent_registry)

        self._logger = logging.getLogger(__name__)

    def register_handlers(self):
        # Home page handlers
        self._app.event("app_home_opened")(self.handle_app_home_opened)

        # Agent handlers
        self._app.action("config_add_agent")(self._wrap_admin_handler(self._agent_config_manager.handle_add_agent))
        self._app.view("config_agent_added_view")(
            self._wrap_admin_handler_with_refresh(self._agent_config_manager.handle_agent_added)
        )
        self._app.action(re.compile(r"^config_agent_menu:"))(
            self._wrap_agent_menu_handler(self._agent_config_manager.handle_agent_menu)
        )
        self._app.view("config_agent_edited_view")(
            self._wrap_admin_handler_with_refresh(self._agent_config_manager.handle_agent_edited)
        )
        self._app.view("config_agent_delete_confirm_view")(
            self._wrap_admin_handler_with_refresh(self._agent_config_manager.handle_agent_delete_confirmed)
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
            agents = await self._agent_config_manager._get_agents()
            is_admin = await self._is_user_admin(user_id)

            view = HomeViewBuilder.build_home_view(
                username=username,
                agents=agents,
                is_admin=is_admin,
            )

            await self._client.views_publish(user_id=user_id, view=view)
        except Exception as e:
            self._logger.error(f"Error refreshing home view for {user_id}: {e}")

    async def _is_user_admin(self, user_id: str) -> bool:
        cached_result = self._admin_cache.get(user_id)
        if cached_result is not None:
            return cached_result

        try:
            response = await self._client.users_info(user=user_id)
            user_info = response["user"]
            is_admin = user_info.get("is_admin", False) or user_info.get("is_owner", False)

            self._admin_cache[user_id] = is_admin
            return is_admin
        except Exception as e:
            self._logger.error(f"Error checking admin status for user {user_id}: {e}")
            return False

    async def _get_user_display_name(self, user_id: str) -> str:
        try:
            response = await self._client.users_info(user=user_id)
            user_info = response["user"]
            return user_info.get("display_name") or user_info.get("real_name") or user_info.get("name", "User")
        except Exception as e:
            self._logger.error(f"Error fetching user info for {user_id}: {e}")
            return "User"

    def _wrap_admin_handler(self, handler):
        """Wrap a handler with admin check."""

        async def wrapper(ack, body, client, *args, **kwargs):
            user_id = body["user"]["id"]
            if not await self._is_user_admin(user_id):
                await ack()
                self._logger.warning(f"Non-admin user {user_id} attempted admin action")
                return
            return await handler(ack, body, client, *args, **kwargs)

        return wrapper

    def _wrap_admin_handler_with_refresh(self, handler):
        """Wrap a handler with admin check and refresh home view after completion."""

        async def wrapper(ack, body, client, view=None, logger=None, *args, **kwargs):
            user_id = body["user"]["id"]
            if not await self._is_user_admin(user_id):
                await ack()
                self._logger.warning(f"Non-admin user {user_id} attempted admin action")
                return
            result = await handler(ack, body, client, view, logger, *args, **kwargs)
            await self.refresh_home_view(user_id)
            return result

        return wrapper

    def _wrap_agent_menu_handler(self, handler):
        """Wrap agent menu handler with conditional admin checks."""

        async def wrapper(ack, body, client, *args, **kwargs):
            user_id = body["user"]["id"]
            selected_option = body["actions"][0]["selected_option"]["value"]
            action, _ = selected_option.split(":", 1)

            if action in ["edit", "delete"]:
                if not await self._is_user_admin(user_id):
                    await ack()
                    self._logger.warning(f"Non-admin user {user_id} attempted admin action: {action}")
                    return

            result = await handler(ack, body, client, *args, **kwargs)

            if action in ["edit", "delete"]:
                await self.refresh_home_view(user_id)

            return result

        return wrapper
