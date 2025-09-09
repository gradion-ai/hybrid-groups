from dataclasses import dataclass, field

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from hygroup.gateway.slack.thread import SlackThread
from hygroup.session import SessionManager


@dataclass
class SlackContext:
    app: AsyncApp
    client: AsyncWebClient
    session_manager: SessionManager
    slack_user_mapping: dict[str, str]
    system_user_mapping: dict[str, str]
    threads: dict[str, SlackThread] = field(default_factory=dict)

    def resolve_system_user_id(self, slack_user_id: str) -> str:
        """Resolve Slack user ID to system user ID."""
        return self.slack_user_mapping.get(slack_user_id, slack_user_id)

    def resolve_slack_user_id(self, system_user_id: str) -> str:
        """Resolve system user ID to Slack user ID."""
        return self.system_user_mapping.get(system_user_id, system_user_id)

    async def send_slack_message(self, thread: SlackThread, text: str, sender: str, **kwargs) -> AsyncSlackResponse:
        if "ts" in kwargs:
            coro = self.client.chat_update
        elif "user" in kwargs:
            coro = self.client.chat_postEphemeral
        else:
            coro = self.client.chat_postMessage

        if sender == "system":
            sender_kwargs = {}
        else:
            sender_emoji = thread.session.agent_registries.get_registry(name=thread.channel_name).get_emoji(sender)
            sender_kwargs = {
                "username": sender,
                "icon_emoji": f":{sender_emoji or 'robot_face'}:",
            }

        return await coro(
            channel=thread.channel_id,
            thread_ts=thread.id,
            text=text,
            **sender_kwargs,
            **kwargs,
        )
