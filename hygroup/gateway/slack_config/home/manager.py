import logging
import re

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent.default.registry import DefaultAgentRegistry
from hygroup.gateway.slack_config.agent.manager import AgentConfigManager
from hygroup.gateway.slack_config.home.views import HomeViewBuilder
from hygroup.gateway.slack_config.policy.manager import ActivationPolicyConfigManager
from hygroup.gateway.slack_config.preferences.manager import UserPreferenceConfigManager
from hygroup.gateway.slack_config.secrets.manager import SecretConfigManager
from hygroup.gateway.slack_config.stores import ActivationPolicyStore, SecretStore, UserPreferencesStore


class SlackHomeManager:
    def __init__(self, client: AsyncWebClient, app: AsyncApp, agent_registry: DefaultAgentRegistry):
        self._client = client
        self._app = app
        self._admin_cache: dict[str, bool] = {}
        self._logger = logging.getLogger(__name__)

        self._secret_store = SecretStore()
        self._activation_policy_store = ActivationPolicyStore()
        self._user_preferences_store = UserPreferencesStore()

        self._secret_config_manager = SecretConfigManager(client, self._secret_store)
        self._agent_config_manager = AgentConfigManager(client, agent_registry)
        self._activation_policy_config_manager = ActivationPolicyConfigManager(client, self._activation_policy_store)
        self._user_preference_config_manager = UserPreferenceConfigManager(client, self._user_preferences_store)

        self.initialize()

    def initialize(self):
        self._secret_store.initialize()
        self._activation_policy_store.initialize()
        self._user_preferences_store.initialize()

    def register_handlers(self):
        # Home page handlers
        self._app.event("app_home_opened")(self.handle_app_home_opened)

        # User secret handlers
        self._app.action("config_add_user_secret")(
            self._wrap_handler(self._secret_config_manager.handle_add_user_secret)
        )
        self._app.view("config_user_secret_added_view")(
            self._wrap_handler_with_refresh(self._secret_config_manager.handle_user_secret_added)
        )
        self._app.action(re.compile(r"^config_user_secret_var_menu:"))(
            self._wrap_handler(self._secret_config_manager.handle_user_secret_menu)
        )
        self._app.view("config_user_secret_edited_view")(
            self._wrap_handler_with_refresh(self._secret_config_manager.handle_user_secret_edited)
        )
        self._app.view("config_user_secret_delete_confirm_view")(
            self._wrap_handler_with_refresh(self._secret_config_manager.handle_user_secret_delete_confirmed)
        )

        # Global secret handlers
        self._app.action("config_add_global_secret")(
            self._wrap_admin_handler(self._secret_config_manager.handle_add_global_secret)
        )
        self._app.view("config_global_secret_added_view")(
            self._wrap_admin_handler_with_refresh(self._secret_config_manager.handle_global_secret_added)
        )
        self._app.action(re.compile(r"^config_global_secret_var_menu:"))(
            self._wrap_admin_handler(self._secret_config_manager.handle_global_secret_menu)
        )
        self._app.view("config_global_secret_edited_view")(
            self._wrap_admin_handler_with_refresh(self._secret_config_manager.handle_global_secret_edited)
        )
        self._app.view("config_global_secret_delete_confirm_view")(
            self._wrap_admin_handler_with_refresh(self._secret_config_manager.handle_global_secret_delete_confirmed)
        )

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

        # Activation policy handlers
        self._app.action("config_activation_policy_overflow")(
            self._wrap_handler(self._activation_policy_config_manager.handle_activation_policy_overflow)
        )
        self._app.action("config_edit_activation_policy")(
            self._wrap_admin_handler(self._activation_policy_config_manager.handle_edit_activation_policy)
        )
        self._app.view("config_activation_policy_edited_view")(
            self._wrap_admin_handler_with_refresh(
                self._activation_policy_config_manager.handle_activation_policy_edited
            )
        )

        # User preference handlers
        self._app.action("config_user_preferences_overflow")(
            self._wrap_handler(self._user_preference_config_manager.handle_user_preferences_overflow)
        )
        self._app.action("config_user_preferences_create")(
            self._wrap_handler(self._user_preference_config_manager.handle_user_preferences_create)
        )
        self._app.view("config_user_preferences_edited_view")(
            self._wrap_handler_with_refresh(self._user_preference_config_manager.handle_user_preferences_edited)
        )

        self._logger.info("All handlers registered")

    async def handle_app_home_opened(self, client, event, logger):
        """Handle app home opened event."""
        self._logger.debug(f"App home opened for user: {event['user']}")

        try:
            user_id = event["user"]
            await self.refresh_home_view(user_id)
        except Exception as e:
            self._logger.error(f"Error handling app home opened: {e}")

    async def refresh_home_view(self, user_id: str):
        """Refresh the home view for a specific user."""
        try:
            username = await self._get_user_display_name(user_id)
            user_secrets = await self._secret_config_manager.get_user_secrets(user_id)
            global_secrets = await self._secret_config_manager.get_global_secrets()
            agents = await self._agent_config_manager._get_agents()
            has_user_preferences = await self._user_preference_config_manager.has_preferences(user_id)
            is_admin = await self._is_user_admin(user_id)

            view = HomeViewBuilder.build_home_view(
                username=username,
                user_id=user_id,
                user_secrets=user_secrets,
                global_secrets=global_secrets,
                agents=agents,
                has_user_preferences=has_user_preferences,
                is_admin=is_admin,
            )

            await self._client.views_publish(user_id=user_id, view=view)

            self._logger.debug(f"Home view refreshed for user: {user_id}")
        except Exception as e:
            self._logger.error(f"Error refreshing home view for {user_id}: {e}")

    async def _is_user_admin(self, user_id: str) -> bool:
        """Check if user has admin or owner privileges."""
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
        """Get the display name for a user."""
        try:
            response = await self._client.users_info(user=user_id)
            user_info = response["user"]
            return user_info.get("display_name") or user_info.get("real_name") or user_info.get("name", "User")
        except Exception as e:
            self._logger.error(f"Error fetching user info for {user_id}: {e}")
            return "User"

    def _wrap_handler(self, handler):
        """Wrap a handler with no additional checks."""

        async def wrapper(ack, body, client, *args, **kwargs):
            return await handler(ack, body, client, *args, **kwargs)

        return wrapper

    def _wrap_handler_with_refresh(self, handler):
        """Wrap a handler and refresh home view after completion."""

        async def wrapper(ack, body, client, view=None, logger=None, *args, **kwargs):
            result = await handler(ack, body, client, view, logger, *args, **kwargs)
            user_id = body["user"]["id"]
            await self.refresh_home_view(user_id)
            return result

        return wrapper

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

            # Only admin actions require admin check
            if action in ["edit", "delete"]:
                if not await self._is_user_admin(user_id):
                    await ack()
                    self._logger.warning(f"Non-admin user {user_id} attempted admin action: {action}")
                    return

            result = await handler(ack, body, client, *args, **kwargs)

            # Refresh view after edit/delete operations
            if action in ["edit", "delete"]:
                await self.refresh_home_view(user_id)

            return result

        return wrapper
