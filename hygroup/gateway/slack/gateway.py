import logging
import os
import re
from typing import Callable

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent import PermissionRequest
from hygroup.channel import RequestHandler
from hygroup.connect.composio import ComposioConnector
from hygroup.gateway import (
    AgentActivation,
    AgentResponse,
    AgentUpdate,
    Gateway,
    MessageAck,
    MessageIgnore,
)
from hygroup.gateway.slack.commands import SlackCommandHandler
from hygroup.gateway.slack.context import SlackContext
from hygroup.gateway.slack.permissions import SlackPermissionHandler
from hygroup.gateway.slack.responses import SlackResponseHandler
from hygroup.gateway.slack.thread import SlackThread
from hygroup.session import Session, SessionFactory


class SlackGateway(Gateway, RequestHandler):
    def __init__(
        self,
        session_factory: SessionFactory,
        composio_connector: ComposioConnector,
        handle_permission_requests: bool = False,
        wip_update_interval: float = 3.0,
        wip_emoji: str = "beer",
    ):
        # original request handler, always used for feedback requests
        self.delegate_handler = session_factory.request_handler

        if handle_permission_requests:
            # this gateway handles permission requests
            session_factory.request_handler = self

        slack_user_mapping = session_factory.settings_store.get_mapping("slack").copy()
        slack_user_mapping[os.environ["SLACK_APP_USER_ID"]] = "system"
        system_user_mapping = {v: k for k, v in slack_user_mapping.items()}

        self._context = SlackContext(
            app=AsyncApp(token=os.environ["SLACK_BOT_TOKEN"]),
            client=AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"]),
            session_factory=session_factory,
            slack_user_mapping=slack_user_mapping,
            system_user_mapping=system_user_mapping,
        )
        self._handler = AsyncSocketModeHandler(self.app, os.environ["SLACK_APP_TOKEN"])

        # Create handlers with their specific dependencies
        self.command_handler = SlackCommandHandler(self._context, composio_connector)
        self.permission_handler = SlackPermissionHandler(self._context)
        self.response_handler = SlackResponseHandler(self._context, wip_emoji, wip_update_interval)

        # register message handler
        self._context.app.message("")(self.handle_slack_message)

        # suppress "unhandled request" log messages
        self.logger = logging.getLogger("slack_bolt.AsyncApp")
        self.logger.setLevel(logging.ERROR)

    @property
    def app(self) -> AsyncApp:
        return self._context.app

    @property
    def client(self) -> AsyncWebClient:
        return self._context.client

    @property
    def threads(self) -> dict[str, SlackThread]:
        return self._context.threads

    @property
    def context(self) -> SlackContext:
        return self._context

    async def start(self, join: bool = True):
        if join:
            await self._handler.start_async()
        else:
            await self._handler.connect_async()

    async def handle_feedback_request(self, *args, **kwargs):
        await self.delegate_handler.handle_feedback_request(*args, **kwargs)

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str, session_id: str):
        await self.permission_handler.handle_permission_request(request, sender, receiver, session_id)

    async def handle_message_ack(self, notification: MessageAck):
        await self.response_handler.handle_message_ack(notification)

    async def handle_message_ignore(self, notification: MessageIgnore):
        await self.response_handler.handle_message_ignore(notification)

    async def handle_agent_activation(self, notification: AgentActivation):
        await self.response_handler.handle_agent_activation(notification)

    async def handle_agent_update(self, notification: AgentUpdate):
        await self.response_handler.handle_agent_update(notification)

    async def handle_agent_response(self, notification: AgentResponse):
        await self.response_handler.handle_agent_response(notification)

    async def handle_slack_message(self, message):
        msg = self._parse_slack_message(message)
        channel_id = msg["channel"]

        if "thread_ts" in message:
            thread_id = message["thread_ts"]
            thread = self.threads.get(thread_id)

            if not thread:
                session = await self._create_session(thread_id=thread_id, channel_id=channel_id)
                thread = self._register_thread(channel_id=channel_id, session=session)

                async with thread.lock:
                    history = await self._load_thread_history(
                        channel_id=channel_id,
                        thread_id=thread_id,
                    )
                    request_ids = await session.request_ids()
                    for entry in history:
                        if entry["id"] not in request_ids:
                            await thread.handle_message(entry)
                    return

            async with thread.lock:
                # FIXME: can run without lock because sync code (?)
                await thread.handle_message(msg)

        else:
            session = await self._create_session(thread_id=msg["id"], channel_id=channel_id)
            thread = self._register_thread(channel_id=channel_id, session=session)

            async with thread.lock:
                await thread.handle_message(msg)

    async def _create_session(self, thread_id: str, channel_id: str) -> Session:
        channel_info = await self.client.conversations_info(channel=channel_id)
        channel_name = channel_info.data["channel"]["name"]
        return self.context.session_factory.create_session(id=thread_id, gateway=self, channel_name=channel_name)

    def _register_thread(self, channel_id: str, session: Session) -> SlackThread:
        thread = SlackThread(channel_id=channel_id, session=session)
        self.threads[session.id] = thread
        return thread

    def _parse_slack_message(self, message: dict) -> dict:
        sender = message["user"]
        sender_resolved = self._context.resolve_system_user_id(sender)

        text_resolved = self._resolve_mentions(message["text"])

        return {
            "id": message["ts"],
            "channel": message.get("channel"),
            "sender": sender_resolved,
            "text": text_resolved,
            "files": message.get("files"),
        }

    def _resolve_mentions(self, text: str | None) -> str:
        if text is None:
            return ""

        return self.resolve_mentions(text, self._context.resolve_system_user_id)

    @staticmethod
    def resolve_mentions(text: str, resolver: Callable[[str], str]) -> str:
        """Finds all mentions in <@userid> formats and replaces them with the resolved
        username (with @ preserved).
        """

        def resolve(match):
            user_id = match.group(1)
            resolved = resolver(user_id)
            return "@" + resolved

        return re.sub(r"<@([/\w-]+)>", resolve, text)

    async def _load_thread_history(self, channel_id: str, thread_id: str) -> list[dict]:
        """Load all messages from a Slack thread except those sent by the installed app.

        Args:
            channel_id: The channel ID where the thread exists
            thread_id: The ID of the thread parent message

        Returns:
            List of Message objects sorted by timestamp (oldest first)
        """
        bot_id = os.getenv("SLACK_BOT_ID")

        msgs = []
        cursor = None

        try:
            while True:
                params = {"channel": channel_id, "ts": thread_id, "limit": 200}

                if cursor:
                    params["cursor"] = cursor

                try:
                    response = await self.client.conversations_replies(**params)
                except Exception as e:
                    self.logger.exception(e)
                    return []

                for message in response["messages"]:
                    if message.get("bot_id") == bot_id:
                        continue

                    msg = self._parse_slack_message(message)
                    msgs.append(msg)

                if not response.get("has_more", False):
                    break

                cursor = response["response_metadata"]["next_cursor"]

            return msgs

        except Exception as e:
            self.logger.error(f"Error loading thread history: {e}")
            return []
