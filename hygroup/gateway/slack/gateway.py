import logging
import os
import re

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent import AgentActivation, AgentResponse, PermissionRequest
from hygroup.channel import RequestHandler
from hygroup.connect.composio import ComposioConnector
from hygroup.gateway.base import Gateway
from hygroup.gateway.slack.commands import SlackCommandHandler
from hygroup.gateway.slack.context import SlackContext
from hygroup.gateway.slack.permissions import SlackPermissionHandler
from hygroup.gateway.slack.responses import SlackResponseHandler
from hygroup.gateway.slack.thread import SlackThread
from hygroup.session import Session, SessionManager


class SlackGateway(Gateway, RequestHandler):
    def __init__(
        self,
        session_manager: SessionManager,
        composio_connector: ComposioConnector,
        handle_permission_requests: bool = False,
        wip_emoji: str = "beer",
        wip_update: bool | None = None,
        wip_update_interval: float = 10.0,
        wip_update_max: int = 10,
    ):
        # original request handler, always used for feedback requests
        self.delegate_handler = session_manager.request_handler

        if handle_permission_requests:
            # this gateway handles permission requests
            session_manager.request_handler = self

        slack_user_mapping = session_manager.settings_store.get_mapping("slack").copy()
        slack_user_mapping[os.environ["SLACK_APP_USER_ID"]] = "system"
        system_user_mapping = {v: k for k, v in slack_user_mapping.items()}

        self._context = SlackContext(
            app=AsyncApp(token=os.environ["SLACK_BOT_TOKEN"]),
            client=AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"]),
            session_manager=session_manager,
            slack_user_mapping=slack_user_mapping,
            system_user_mapping=system_user_mapping,
        )
        self._handler = AsyncSocketModeHandler(self.app, os.environ["SLACK_APP_TOKEN"])

        # sensible default for wip_update if not defined.
        wip_update = not handle_permission_requests if wip_update is None else wip_update

        # Create handlers with their specific dependencies
        self.command_handler = SlackCommandHandler(self._context, composio_connector)
        self.permission_handler = SlackPermissionHandler(self._context)
        self.response_handler = SlackResponseHandler(
            self._context,
            wip_emoji=wip_emoji,
            wip_update=wip_update,
            wip_update_interval=wip_update_interval,
            wip_update_max=wip_update_max,
        )

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

    async def handle_agent_activation(self, activation: AgentActivation, session_id: str):
        await self.response_handler.handle_agent_activation(activation, session_id)

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        await self.response_handler.handle_agent_response(response, sender, receiver, session_id)

    async def handle_slack_message(self, message):
        msg = self._parse_slack_message(message)

        if "thread_ts" in message:
            thread_id = message["thread_ts"]
            thread = self.threads.get(thread_id)

            if not thread:
                if session := await self._context.session_manager.load_session(id=thread_id):
                    thread = await self._register_slack_thread(channel_id=msg["channel"], session=session)
                else:
                    session = self._context.session_manager.create_session(id=thread_id)
                    thread = await self._register_slack_thread(channel_id=msg["channel"], session=session)

                async with thread.lock:
                    history = await self._load_thread_history(
                        channel=msg["channel"],
                        thread_ts=thread_id,
                    )
                    for entry in history:
                        await thread.handle_message(entry)
                    return

            async with thread.lock:
                await thread.handle_message(msg)

        else:
            session = self._context.session_manager.create_session(id=msg["id"])
            thread = await self._register_slack_thread(channel_id=msg["channel"], session=session)

            async with thread.lock:
                await thread.handle_message(msg)

    async def _register_slack_thread(self, channel_id: str, session: Session) -> SlackThread:
        channel_info = await self.client.conversations_info(channel=channel_id)
        channel_name = channel_info.data["channel"]["name"]

        session.set_gateway(self)
        session.set_channel(channel_name)
        session.sync()

        self.threads[session.id] = SlackThread(
            channel_id=channel_id,
            session=session,
        )
        return self.threads[session.id]

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
        """Finds all mentions in <@userid> formats and replaces them with the resolved
        username (with @ preserved).
        """
        if text is None:
            return ""

        def resolve(match):
            user_id = match.group(1)
            resolved = self._context.resolve_system_user_id(user_id)
            return "@" + resolved

        return re.sub(r"<@([/\w-]+)>", resolve, text)

    async def _load_thread_history(self, channel: str, thread_ts: str) -> list[dict]:
        """Load all messages from a Slack thread except those sent by the installed app.

        Args:
            channel: The channel ID where the thread exists
            thread_ts: The timestamp of the thread parent message

        Returns:
            List of Message objects sorted by timestamp (oldest first)
        """
        bot_id = os.getenv("SLACK_BOT_ID")

        msgs = []
        cursor = None

        try:
            while True:
                params = {"channel": channel, "ts": thread_ts, "limit": 200}

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
