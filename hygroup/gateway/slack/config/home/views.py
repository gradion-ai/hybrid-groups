from typing import Any, Dict, List

from hygroup.gateway.slack.config.agent.views import AgentViewBuilder
from hygroup.gateway.slack.config.models import AgentListViewModel


class HomeViewBuilder:
    @staticmethod
    def build_home_view(
        username: str,
        agents: List[AgentListViewModel],
        is_admin: bool,
    ) -> Dict[str, Any]:
        blocks = []

        # Welcome section
        if is_admin:
            intro_text = "This is a your Hybrid Groups home page!\nHere you can manage the configured agents and create new ones."
        else:
            intro_text = "This is a your Hybrid Groups home page!\nHere you can inspect the available agents."

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

        # Agents section
        blocks.extend(AgentViewBuilder.build_agents_section(agents, is_admin))

        return {
            "type": "home",
            "blocks": blocks,
        }
