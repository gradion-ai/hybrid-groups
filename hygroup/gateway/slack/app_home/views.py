from typing import Any

from hygroup.gateway.slack.app_home.agent.views import AgentViewBuilder
from hygroup.gateway.slack.app_home.models import AgentListViewModel
from hygroup.gateway.slack.app_home.policy.views import ActivationPolicyViewBuilder
from hygroup.gateway.slack.app_home.preferences.views import UserPreferenceViewBuilder
from hygroup.gateway.slack.app_home.secrets.views import SecretViewBuilder


class HomeViewBuilder:
    @staticmethod
    def build_home_view(
        app_name: str | None,
        username: str,
        user_secrets: dict[str, str],
        user_preferences: str | None,
        agents: list[AgentListViewModel],
        is_system_editor: bool,
    ) -> dict[str, Any]:
        blocks = []

        # Welcome section
        app_name_text = f" for `{app_name}`" if app_name else ""
        intro_text = f"This is the settings page{app_name_text}.\n\nConfigure your *personal secrets and preferences* and {'manage' if is_system_editor else 'view'} the *shared agent settings*{' and the *activation policy*' if is_system_editor else ''}."

        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Welcome, {username}* 👋\n\n{intro_text}",
                    },
                },
            ]
        )

        blocks.extend(
            [
                {"type": "section", "text": {"type": "plain_text", "text": " "}},
                {"type": "section", "text": {"type": "plain_text", "text": " "}},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "👤 Personal Settings",
                        "emoji": True,
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Personal settings that only apply to you.",
                    },
                },
            ]
        )

        # User secrets section
        blocks.extend(SecretViewBuilder.build_user_secrets_section(user_secrets))

        # User preferences section
        blocks.extend(UserPreferenceViewBuilder.build_user_preferences_section(user_preferences))

        blocks.extend(
            [
                {"type": "section", "text": {"type": "plain_text", "text": " "}},
                {"type": "section", "text": {"type": "plain_text", "text": " "}},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🌐 Shared Settings",
                        "emoji": True,
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Shared settings that apply to all members of this workspace.",
                    },
                },
            ]
        )

        # Agents section
        blocks.extend(AgentViewBuilder.build_agents_section(agents, is_system_editor))

        # Activation policy section
        if is_system_editor:
            blocks.extend(ActivationPolicyViewBuilder.build_activation_policy_section(is_system_editor))

        return {
            "type": "home",
            "blocks": blocks,
        }
