import logging
import os
from asyncio import Lock
from dataclasses import dataclass

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent import AgentRequest, AgentResponse, Message
from hygroup.gateway.base import Gateway
from hygroup.gateway.utils import extract_mention, extract_thread_references, format_response, replace_all_mentions
from hygroup.session import Session, SessionManager


@dataclass
class SlackThread:
    channel: str
    session: Session
    lock: Lock = Lock()

    @property
    def id(self) -> str:
        return self.session.id

    async def handle_message(self, msg: dict):
        if self.session.contains(msg["id"]):
            return

        if msg["receiver_resolved"] in await self.session.agent_names():
            await self._invoke_agent(
                query=msg["text"],
                sender=msg["sender_resolved"],
                receiver=msg["receiver_resolved"],
                thread_refs=msg["thread_refs"],
                message_id=msg["id"],
            )
        else:
            await self.session.update(
                Message(
                    sender=msg["sender_resolved"],
                    receiver=msg["receiver_resolved"],
                    text=msg["text"],
                    id=msg["id"],
                )
            )

    async def _invoke_agent(
        self,
        query: str,
        sender: str,
        receiver: str,
        thread_refs: list[str],
        message_id: str | None = None,
    ):
        threads = await self.session.manager.load_threads(thread_refs)
        request = AgentRequest(query=query, sender=sender, threads=threads, id=message_id)
        await self.session.invoke(request=request, receiver=receiver)


class SlackGateway(Gateway):
    def __init__(
        self,
        session_manager: SessionManager,
        user_mapping: dict[str, str] = {},
    ):
        self.session_manager = session_manager

        # maps from slack user id to core user id
        self._slack_user_mapping = user_mapping
        # maps from core user id to slack user id
        self._core_user_mapping = {v: k for k, v in user_mapping.items()}

        self._app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
        self._client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])
        self._handler = AsyncSocketModeHandler(self._app, os.environ["SLACK_APP_TOKEN"])
        self._threads: dict[str, SlackThread] = {}

        # register event handlers
        self._app.message("")(self.handle_slack_message)

        # Suppress "unhandled request" log messages
        self.logger = logging.getLogger("slack_bolt.AsyncApp")
        self.logger.setLevel(logging.ERROR)

    async def start(self, join: bool = True):
        if join:
            await self._handler.start_async()
        else:
            await self._handler.connect_async()

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        thread = self._threads[session_id]

        receiver_resolved = self._resolve_slack_user_id(receiver)
        receiver_resolved_formatted = f"<@{receiver_resolved}>"

        await self._post_slack_message(
            thread, f"{receiver_resolved_formatted} {format_response(response.text, response.handoffs)}", sender
        )

    async def _post_slack_message(self, thread: SlackThread, text: str, sender: str, **kwargs):
        await self._client.chat_postMessage(
            channel=thread.channel,
            thread_ts=thread.id,
            text=text,
            username=sender,
            icon_emoji=":robot_face:",
            **kwargs,
        )

    async def handle_slack_message(self, message):
        msg = self._parse_slack_message(message)

        if "thread_ts" in message:
            thread_id = message["thread_ts"]
            thread = self._threads.get(thread_id)

            if not thread:
                if session := await self.session_manager.load_session(id=thread_id):
                    thread = self._register_slack_thread(channel_id=msg["channel"], session=session)
                else:
                    session = self.session_manager.create_session(id=thread_id)
                    thread = self._register_slack_thread(channel_id=msg["channel"], session=session)

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
            session = self.session_manager.create_session(id=msg["id"])
            thread = self._register_slack_thread(channel_id=msg["channel"], session=session)

            async with thread.lock:
                await thread.handle_message(msg)

    async def _registered_agent_names(self) -> set[str]:
        if self.session_manager.agent_registry:
            return await self.session_manager.agent_registry.get_registered_names()
        return set()

    def _register_slack_thread(self, channel_id: str, session: Session) -> SlackThread:
        session.set_gateway(self)
        session.sync()
        self._threads[session.id] = SlackThread(
            channel=channel_id,
            session=session,
        )
        return self._threads[session.id]

    def _resolve_core_user_id(self, slack_user_id: str) -> str:
        return self._slack_user_mapping.get(slack_user_id, slack_user_id)

    def _resolve_slack_user_id(self, core_user_id: str) -> str:
        return self._core_user_mapping.get(core_user_id, core_user_id)

    def _parse_slack_message(self, message: dict) -> dict:
        sender = message["user"]
        sender_resolved = self._resolve_core_user_id(sender)
        receiver, text = extract_mention(message["text"])
        receiver_resolved = None if receiver is None else self._resolve_core_user_id(receiver)
        text = replace_all_mentions(text, self._resolve_core_user_id)
        thread_refs = extract_thread_references(text)
        return {
            "id": message["ts"],
            "channel": message.get("channel"),
            "sender": sender,
            "sender_resolved": sender_resolved,
            "receiver": receiver,
            "receiver_resolved": receiver_resolved,
            "text": text,
            "thread_refs": thread_refs,
        }

    async def _load_thread_history(self, channel: str, thread_ts: str) -> list[dict]:
        """Load all messages from a Slack thread.

        Args:
            channel: The channel ID where the thread exists
            thread_ts: The timestamp of the thread parent message

        Returns:
            List of Message objects sorted by timestamp (oldest first)
        """
        msgs = []
        cursor = None

        try:
            while True:
                params = {"channel": channel, "ts": thread_ts, "limit": 200}

                if cursor:
                    params["cursor"] = cursor

                response = await self._client.conversations_replies(**params)

                for message in response["messages"]:
                    # Skip bot messages and messages without a user
                    if message.get("subtype") == "bot_message" or "user" not in message:
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
