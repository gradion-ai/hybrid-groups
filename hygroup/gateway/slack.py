import logging
import os
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

    @property
    def id(self) -> str:
        return self.session.id


class SlackGateway(Gateway):
    def __init__(
        self,
        session_manager: SessionManager,
        user_mapping: dict[str, str] = {},
        app_id: str = "U08LHFS3SE9",
    ):
        if app_id not in user_mapping:
            raise ValueError(f"app_id {app_id} not in user_mapping")

        self.session_manager = session_manager
        self.app_id = app_id

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
        logging.getLogger("slack_bolt.AsyncApp").setLevel(logging.ERROR)

    def resolve_core_user_id(self, slack_user_id: str) -> str:
        return self._slack_user_mapping.get(slack_user_id, slack_user_id)

    def resolve_slack_user_id(self, core_user_id: str) -> str:
        return self._core_user_mapping.get(core_user_id, core_user_id)

    async def start(self, join: bool = True):
        if join:
            await self._handler.start_async()
        else:
            await self._handler.connect_async()

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        thread = self._threads[session_id]

        receiver_resolved = self.resolve_slack_user_id(receiver)
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
        """Handle message from Slack user."""
        channel = message["channel"]

        # Slack id of the user who sent the message
        sender = message["user"]
        # Resolve sender to internal user name
        sender_resolved = self.resolve_core_user_id(sender)

        # Extract receiver (leading mention, if any) and remaining text
        receiver, text = extract_mention(message["text"])
        # Resolve receiver to internal user or agent name
        receiver_resolved = None if receiver is None else self.resolve_core_user_id(receiver)

        # Replace all mentions in text with internal user and agent names
        text = replace_all_mentions(text, self.resolve_core_user_id)

        # Extract thread ids (format: thread:thread_id) from text.
        thread_refs = extract_thread_references(text)

        if "thread_ts" in message:
            thread_id = message["thread_ts"]
            thread = self._threads.get(thread_id)

            if not thread:
                if session := await self.session_manager.load_session(id=thread_id):
                    thread = self.register_thread(channel_id=channel, session=session)
                    session.sync()
                else:
                    return

            if receiver_resolved in await thread.session.agent_names():
                # invoke agent identified by receiver_resolved
                await self.invoke_agent(
                    query=text,
                    sender=sender_resolved,
                    receiver=receiver_resolved,
                    thread_refs=thread_refs,
                    thread=thread,
                )
            else:
                # a known or unknown user is mentioned or it's simply a plain message without a mention
                await thread.session.update(Message(sender=sender_resolved, receiver=receiver_resolved, text=text))
        elif self.app_id == receiver:
            # create a new session and turn on sync
            session = self.session_manager.create_session(id=message["ts"])
            session.sync()

            # register new session as Slack thread in gateway
            thread = self.register_thread(channel_id=channel, session=session)

            # invoke agent associated with the slack app
            await self.invoke_agent(
                query=text,
                sender=sender_resolved,
                receiver=receiver_resolved,  # type: ignore
                thread_refs=thread_refs,
                thread=thread,
            )

    async def invoke_agent(self, query: str, sender: str, receiver: str, thread_refs: list[str], thread: SlackThread):
        threads = await self.session_manager.load_threads(thread_refs)
        request = AgentRequest(query=query, sender=sender, threads=threads)
        await thread.session.invoke(request=request, receiver=receiver)

    def register_thread(self, channel_id: str, session: Session) -> SlackThread:
        session.set_gateway(self)
        self._threads[session.id] = SlackThread(
            channel=channel_id,
            session=session,
        )
        return self._threads[session.id]
