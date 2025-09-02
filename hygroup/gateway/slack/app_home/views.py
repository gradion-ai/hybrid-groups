from typing import Any

from hygroup.gateway.slack.app_home.preferences.views import UserPreferenceViewBuilder
from hygroup.gateway.slack.app_home.secrets.views import SecretViewBuilder


class HomeViewBuilder:
    @staticmethod
    def build_home_view(
        app_name: str | None,
        username: str,
        user_secrets: dict[str, str],
        user_preferences: str | None,
    ) -> dict[str, Any]:
        blocks = []

        # Welcome section
        blocks.extend(
            [
                {"type": "section", "text": {"type": "plain_text", "text": " "}},
                {"type": "section", "text": {"type": "plain_text", "text": " "}},
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"👤 Personal settings for {username}",
                        "emoji": True,
                    },
                },
            ]
        )

        # User preferences section
        blocks.extend(UserPreferenceViewBuilder.build_user_preferences_section(user_preferences))

        # User secrets section
        blocks.extend(SecretViewBuilder.build_user_secrets_section(user_secrets))

        return {
            "type": "home",
            "blocks": blocks,
        }
