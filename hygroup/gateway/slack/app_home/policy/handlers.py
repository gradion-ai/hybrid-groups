import logging
from pathlib import Path

import aiofiles
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent.select.agent import AgentSelectorSettings
from hygroup.gateway.slack.app_home.policy.views import ActivationPolicyViewBuilder

logger = logging.getLogger(__name__)


class ActivationPolicyConfigHandlers:
    def __init__(self, client: AsyncWebClient, selector_settings: AgentSelectorSettings):
        self._client = client
        self._selector_settings = selector_settings

    def _custom_policy_file(self) -> Path | None:
        if not self._selector_settings.instructions_file:
            return None
        if isinstance(self._selector_settings.instructions_file, str):
            return Path(self._selector_settings.instructions_file)
        return self._selector_settings.instructions_file

    async def get_custom_policy(self) -> str | None:
        custom_policy_file = self._custom_policy_file()
        if custom_policy_file and custom_policy_file.exists():
            async with aiofiles.open(custom_policy_file, "r") as f:
                return await f.read()
        return None

    async def _set_custom_policy(self, policy: str):
        async with aiofiles.open(self._custom_policy_file(), "w") as f:
            await f.write(policy)

    async def handle_activation_policy_overflow(self, ack, body, client):
        await ack()

        selected_option = body["actions"][0]["selected_option"]["value"]
        if selected_option == "home_view_activation_policy":
            await self._handle_view_activation_policy_internal(body)
        elif selected_option == "home_edit_activation_policy":
            await self._handle_edit_activation_policy_internal(body)

    async def _handle_view_activation_policy_internal(self, body):
        policy = await self.get_custom_policy()
        modal = ActivationPolicyViewBuilder.build_activation_policy_view_modal(policy)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def _handle_edit_activation_policy_internal(self, body):
        policy = await self.get_custom_policy()
        modal = ActivationPolicyViewBuilder.build_activation_policy_edit_modal(policy)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_edit_activation_policy(self, ack, body, client):
        await ack()

        policy = await self.get_custom_policy()
        modal = ActivationPolicyViewBuilder.build_activation_policy_edit_modal(policy)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_activation_policy_edited(self, ack, body, client, view, slack_logger):
        content = view["state"]["values"]["policy_content"]["content_input"]["value"]

        if not content or not content.strip():
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "policy_content": "Policy content cannot be empty",
                    },
                }
            )
            return

        try:
            await self._set_custom_policy(content.strip())
            await ack()
            logger.info("Activation policy updated successfully")
        except Exception as e:
            logger.error(f"Error updating activation policy: {e}")
            await ack(
                {
                    "response_action": "errors",
                    "errors": {
                        "policy_content": "Failed to update policy. Please try again.",
                    },
                }
            )
