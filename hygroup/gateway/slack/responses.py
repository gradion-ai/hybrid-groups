from markdown_to_mrkdwn import SlackMarkdownConverter

from hygroup.gateway import (
    AgentActivation,
    AgentResponse,
    AgentUpdate,
    MessageAck,
    MessageIgnore,
)
from hygroup.gateway.slack.context import SlackContext
from hygroup.gateway.slack.thread import SlackThread
from hygroup.gateway.slack.utils import BurstBuffer


class SlackResponseHandler:
    def __init__(
        self,
        context: SlackContext,
        wip_emoji: str = "beer",
        wip_update_interval: float = 3.0,
    ):
        self.converter = SlackMarkdownConverter()
        self.context = context

        self.wip_emoji = wip_emoji
        self.wip_update_interval = wip_update_interval

    async def handle_message_ack(self, notification: MessageAck):
        thread = self.context.threads[notification.session_id]

        if request_id := notification.request_id:
            await self.context.client.reactions_add(
                channel=thread.channel_id,
                timestamp=request_id,
                name="eyes",
            )

    async def handle_message_ignore(self, notification: MessageIgnore):
        thread = self.context.threads[notification.session_id]

        if request_id := notification.request_id:
            await self.context.client.reactions_add(
                channel=thread.channel_id,
                timestamp=request_id,
                name="ballot_box_with_check",
            )

    async def handle_agent_activation(self, notification: AgentActivation):
        thread = self.context.threads[notification.session_id]

        if request_id := notification.request_id:
            response = await self._send_wip_message(thread, notification.sender, notification.receiver)
            wip_message_id = response.data["ts"]

            num_sub_calls: int = 0
            num_tool_calls: int = 0

            async def update_wip_message(updates: list[AgentUpdate]):
                nonlocal num_sub_calls
                nonlocal num_tool_calls

                for update in updates:
                    if update.tool_name == "run_subagent":
                        num_sub_calls += 1
                    else:
                        num_tool_calls += 1

                await self._send_wip_message(
                    thread=thread,
                    sender=notification.sender,
                    receiver=notification.receiver,
                    num_sub_calls=num_sub_calls,
                    num_tool_calls=num_tool_calls,
                    ts=wip_message_id,
                )

            thread.wip_message_ids[request_id] = wip_message_id
            thread.wip_update_buffers[request_id] = BurstBuffer(update_wip_message, self.wip_update_interval)

    async def handle_agent_update(self, notification: AgentUpdate):
        """Handle agent update messages."""

        if request_id := notification.request_id:
            thread = self.context.threads[notification.session_id]
            buffer = thread.wip_update_buffers[request_id]
            buffer.update(notification)

    async def handle_agent_response(self, notification: AgentResponse):
        """Handle agent response messages."""
        thread = self.context.threads[notification.session_id]

        if request_id := notification.request_id:
            await self.context.client.reactions_add(
                channel=thread.channel_id,
                timestamp=notification.request_id,
                name="robot_face",
            )

            if buffer := thread.wip_update_buffers.pop(request_id, None):
                buffer.cancel()

            if response_id := thread.wip_message_ids.pop(request_id, None):
                await self.context.client.chat_delete(
                    channel=thread.channel_id,
                    thread_ts=thread.id,
                    ts=response_id,
                )

        receiver_resolved = self.context.resolve_slack_user_id(notification.receiver)
        receiver_resolved_formatted = f"<@{receiver_resolved}>"

        text = f"{receiver_resolved_formatted} {notification.text}"

        # Truncate message if it exceeds Slack's character limit
        if len(text) > 2990:
            text = text[:2990] + "..."

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": self.converter.convert(text),
                },
            },
        ]
        await self.context.send_slack_message(thread, text, notification.sender, blocks=blocks)

    async def _send_wip_message(
        self,
        thread: SlackThread,
        sender: str,
        receiver: str,
        num_sub_calls: int = 0,
        num_tool_calls: int = 0,
        **kwargs,
    ):
        beer = f":{self.wip_emoji}:"

        receiver_resolved = self.context.resolve_slack_user_id(receiver)
        receiver_resolved_formatted = f"<@{receiver_resolved}>"

        update_text = f"- `{num_sub_calls}` subagent calls \n- `{num_tool_calls}` tools calls"
        text = f"{beer} *Brewing for* {receiver_resolved_formatted}\n\n{update_text}"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": self.converter.convert(text),
                },
            },
        ]

        return await self.context.send_slack_message(thread, text, sender, blocks=blocks, **kwargs)
