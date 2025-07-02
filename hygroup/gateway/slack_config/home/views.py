from typing import Any, Dict, List

from hygroup.gateway.slack_config.agent.views import AgentViewBuilder
from hygroup.gateway.slack_config.models import AgentListViewModel
from hygroup.gateway.slack_config.policy.views import ActivationPolicyViewBuilder
from hygroup.gateway.slack_config.preferences.views import UserPreferenceViewBuilder
from hygroup.gateway.slack_config.secrets.views import SecretViewBuilder


class HomeViewBuilder:
    @staticmethod
    def build_home_view(
        username: str,
        user_id: str,
        user_secrets: Dict[str, str],
        global_secrets: Dict[str, str],
        agents: List[AgentListViewModel],
        has_user_preferences: bool,
        is_admin: bool,
    ) -> Dict[str, Any]:
        blocks = []

        # Welcome section
        if is_admin:
            intro_text = "This is a your Hybrid Groups home page!\nHere you can manage your personal secrets and preferences. As an admin you can also configure agents, global secrets and the activation policy."
        else:
            intro_text = "This is a your Hybrid Groups home page!\nHere you can manage your personal secrets and preferences. You can also inspect the available agents and the activation policy."

        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"👋 *Welcome, {username}!*",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": intro_text,
                    },
                },
            ]
        )

        # User secrets section
        blocks.extend(SecretViewBuilder.build_user_secrets_section(user_secrets))

        # User preferences section
        blocks.extend(UserPreferenceViewBuilder.build_user_preferences_section(user_id, has_user_preferences))

        # Global secrets section (admin only)
        if is_admin:
            blocks.extend(SecretViewBuilder.build_global_secrets_section(global_secrets))

        # Agents section
        blocks.extend(AgentViewBuilder.build_agents_section(agents, is_admin))

        # Activation policy section
        blocks.extend(ActivationPolicyViewBuilder.build_activation_policy_section(is_admin))

        return {
            "type": "home",
            "blocks": blocks,
        }
