import asyncio

from markdown_to_mrkdwn import SlackMarkdownConverter

from hygroup.agent import AgentActivation, AgentResponse
from hygroup.gateway.slack.context import SlackContext
from hygroup.gateway.slack.thread import SlackThread


class SlackResponseHandler:
    def __init__(
        self,
        context: SlackContext,
        wip_emoji: str = "beer",
        wip_update: bool = True,
        wip_update_interval: float = 10.0,
        wip_update_max: int = 10,
    ):
        self.converter = SlackMarkdownConverter()
        self.context = context
        self.wip_emoji = wip_emoji
        self.wip_update = wip_update
        self.wip_update_interval = wip_update_interval
        self.wip_update_max = wip_update_max

    async def handle_agent_activation(self, activation: AgentActivation, thread_id: str):
        """Handle agent activation with emoji reactions and WIP messages."""
        thread = self.context.threads[thread_id]
        if activation.message_id:
            await self.context.client.reactions_add(
                channel=thread.channel_id,
                timestamp=activation.message_id,
                name="eyes",
            )

        if activation.request_id:
            response = await self._send_wip_message(thread, activation.agent_name)
            response_id = response.data["ts"]

            thread.response_ids[activation.request_id] = response_id

            if self.wip_update:
                wip_coro = self._update_wip_message(
                    thread=thread,
                    sender=activation.agent_name,
                    message_id=response_id,
                )
                thread.response_upd[activation.request_id] = asyncio.create_task(wip_coro)

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, thread_id: str):
        """Handle agent response messages."""
        thread = self.context.threads[thread_id]
        if response.message_id:
            await self.context.client.reactions_add(
                channel=thread.channel_id,
                timestamp=response.message_id,
                name="robot_face" if response.text else "ballot_box_with_check",
            )

        if request_id := response.request_id:
            if wip_task := thread.response_upd.pop(request_id, None):
                wip_task.cancel()
                try:
                    await wip_task
                except asyncio.CancelledError:
                    pass

            if response_id := thread.response_ids.pop(request_id, None):
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

    async def _update_wip_message(self, thread: SlackThread, sender: str, message_id: str):
        try:
            for i in range(2, self.wip_update_max):
                await asyncio.sleep(self.wip_update_interval)
                await self._send_wip_message(thread, sender, i, ts=message_id)
        except asyncio.CancelledError:
            pass

    async def _send_wip_message(self, thread: SlackThread, sender: str, progress: int = 1, **kwargs):
        beers = f":{self.wip_emoji}:" * progress
        text = f"{beers} *brewing ...*"
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
