import logging
from typing import Optional

from slack_sdk.web.async_client import AsyncWebClient

from hygroup.gateway.slack_config.models import ActivationPolicyViewModel
from hygroup.gateway.slack_config.policy.views import ActivationPolicyViewBuilder
from hygroup.gateway.slack_config.stores import ActivationPolicyStore

logger = logging.getLogger(__name__)


class ActivationPolicyConfigManager:
    def __init__(self, client: AsyncWebClient, store: ActivationPolicyStore):
        self._client = client
        self._store = store

    async def get_policy(self) -> Optional[ActivationPolicyViewModel]:
        return await self._store.get()

    async def handle_activation_policy_overflow(self, ack, body, client):
        logger.debug("Handle activation policy overflow")
        await ack()

        # Get the selected option value
        selected_option = body["actions"][0]["selected_option"]["value"]

        if selected_option == "config_view_activation_policy":
            await self._handle_view_activation_policy_internal(body)
        elif selected_option == "config_edit_activation_policy":
            await self._handle_edit_activation_policy_internal(body)

    async def _handle_view_activation_policy_internal(self, body):
        logger.debug("Handle view activation policy")

        # Get current policy
        current_policy = await self._store.get()

        # Build and open view modal
        modal = ActivationPolicyViewBuilder.build_activation_policy_view_modal(current_policy)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def _handle_edit_activation_policy_internal(self, body):
        logger.debug("Handle edit activation policy")

        # Get current policy
        current_policy = await self._store.get()

        # Build and open edit modal
        modal = ActivationPolicyViewBuilder.build_activation_policy_edit_modal(current_policy)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_edit_activation_policy(self, ack, body, client):
        logger.debug("Handle edit activation policy")
        await ack()

        # Get current policy
        current_policy = await self._store.get()

        # Build and open modal
        modal = ActivationPolicyViewBuilder.build_activation_policy_edit_modal(current_policy)
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
            # Update policy in store
            await self._store.update(content.strip())
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
