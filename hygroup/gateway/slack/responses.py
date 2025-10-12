from markdown_to_mrkdwn import SlackMarkdownConverter

from hygroup.agent import AgentActivation, AgentResponse, AgentUpdate
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

    async def handle_agent_activation(self, activation: AgentActivation, sender: str, receiver: str, thread_id: str):
        """Handle agent activation with emoji reactions and WIP messages."""
        thread = self.context.threads[thread_id]
        if activation.request_id:
            await self.context.client.reactions_add(
                channel=thread.channel_id,
                timestamp=activation.request_id,
                name="eyes",
            )

        if request_id := activation.request_id:
            response = await self._send_wip_message(thread, sender, receiver)
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
                    sender=sender,
                    receiver=receiver,
                    num_sub_calls=num_sub_calls,
                    num_tool_calls=num_tool_calls,
                    ts=wip_message_id,
                )

            thread.wip_message_ids[request_id] = wip_message_id
            thread.wip_update_buffers[request_id] = BurstBuffer(update_wip_message, self.wip_update_interval)

    async def handle_agent_update(self, update: AgentUpdate, sender: str, receiver: str, thread_id: str):
        """Handle agent update messages."""

        if request_id := update.request_id:
            thread = self.context.threads[thread_id]
            buffer = thread.wip_update_buffers[request_id]
            buffer.update(update)

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, thread_id: str):
        """Handle agent response messages."""
        thread = self.context.threads[thread_id]
        if response.request_id:
            await self.context.client.reactions_add(
                channel=thread.channel_id,
                timestamp=response.request_id,
                name="robot_face" if response.text else "ballot_box_with_check",
            )

        if request_id := response.request_id:
            if buffer := thread.wip_update_buffers.pop(request_id, None):
                buffer.cancel()

            if response_id := thread.wip_message_ids.pop(request_id, None):
                await self.context.client.chat_delete(
                    channel=thread.channel_id,
                    thread_ts=thread.id,
                    ts=response_id,
                )

        if not response.text:
            return

        receiver_resolved = self.context.resolve_slack_user_id(receiver)
        receiver_resolved_formatted = f"<@{receiver_resolved}>"

        text = f"{receiver_resolved_formatted} {response.text}"

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
        await self.context.send_slack_message(thread, text, sender, blocks=blocks)

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

        update_text = f"- `{num_sub_calls}` subagent delgations \n- `{num_tool_calls}` actions executed"
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
