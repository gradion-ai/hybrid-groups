import logging
import os
from asyncio import Lock
from dataclasses import dataclass, field
from uuid import uuid4

from markdown_to_mrkdwn import SlackMarkdownConverter
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent import (
    AgentRequest,
    AgentResponse,
    Message,
    PermissionRequest,
)
from hygroup.gateway.base import Gateway
from hygroup.gateway.utils import extract_initial_mention, resolve_mentions
from hygroup.session import Session, SessionManager
from hygroup.user import RequestHandler


@dataclass
class SlackThread:
    channel: str
    session: Session
    permission_requests: dict[str, PermissionRequest] = field(default_factory=dict)
    activated: bool = False
    lock: Lock = Lock()

    @property
    def id(self) -> str:
        return self.session.id

    async def handle_message(self, msg: dict):
        if self.session.contains(msg["id"]):
            return  # idempotency

        if msg["receiver_resolved"] in await self.session.agent_names():
            await self._invoke_agent(
                query=msg["text"],
                sender=msg["sender_resolved"],
                receiver=msg["receiver_resolved"],
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
        message_id: str | None = None,
    ):
        request = AgentRequest(query=query, sender=sender, id=message_id)
        await self.session.invoke(request=request, receiver=receiver)


class SlackGateway(Gateway, RequestHandler):
    def __init__(
        self,
        session_manager: SessionManager,
        user_mapping: dict[str, str] = {},
        handle_permission_requests: bool = False,
    ):
        self.session_manager = session_manager
        self.delegate_handler = session_manager.request_handler

        if handle_permission_requests:
            # Gateway handles permission requests itself, delegating
            # all other requests to the original request handler.
            self.session_manager.request_handler = self

        # maps from slack user id to system user id
        self._slack_user_mapping = user_mapping
        # maps from system user id to slack user id
        self._system_user_mapping = {v: k for k, v in user_mapping.items()}

        self._app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
        self._client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])
        self._handler = AsyncSocketModeHandler(self._app, os.environ["SLACK_APP_TOKEN"])
        self._converter = SlackMarkdownConverter()
        self._threads: dict[str, SlackThread] = {}

        # register event handlers
        self._app.message("")(self.handle_slack_message)
        self._app.action("once_button")(self.handle_permission_response)
        self._app.action("session_button")(self.handle_permission_response)
        self._app.action("always_button")(self.handle_permission_response)
        self._app.action("deny_button")(self.handle_permission_response)

        # Suppress "unhandled request" log messages
        self.logger = logging.getLogger("slack_bolt.AsyncApp")
        self.logger.setLevel(logging.ERROR)

    @property
    def app(self) -> AsyncApp:
        return self._app

    @property
    def client(self) -> AsyncWebClient:
        return self._client

    async def start(self, join: bool = True):
        if join:
            await self._handler.start_async()
        else:
            await self._handler.connect_async()

    async def handle_feedback_request(self, *args, **kwargs):
        await self.delegate_handler.handle_feedback_request(*args, **kwargs)

    async def handle_confirmation_request(self, *args, **kwargs):
        await self.delegate_handler.handle_confirmation_request(*args, **kwargs)

    async def handle_agent_activation(self, agent_name: str | None, message_id: str, session_id: str):
        thread = self._threads[session_id]

        match agent_name:
            case None:
                emoji = "ballot_box_with_check"
            case "selector":
                emoji = "eyes"
            case _:
                emoji = "robot_face"

        await self._client.reactions_add(
            channel=thread.channel,
            timestamp=message_id,
            name=emoji,
        )

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        thread = self._threads[session_id]

        receiver_resolved = self._resolve_slack_user_id(receiver)
        receiver_resolved_formatted = f"<@{receiver_resolved}>"

        response_text = response.text
        if response.handoffs:
            response_text += "\n\n**Handoffs:**"
            for agent, query in response.handoffs.items():
                response_text += f"\n- `{agent}`: {query}"

        text = f"{receiver_resolved_formatted} {response_text}"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": self._converter.convert(text),
                },
            },
        ]
        await self._post_slack_message(thread, text, sender, blocks=blocks)

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str, session_id: str):  # type: ignore
        corr_id = str(uuid4())

        thread = self._threads[session_id]
        thread.permission_requests[corr_id] = request

        # A more robust approach would be https://api.slack.com/methods/conversations.replies
        # to determine if there is an active thread, but it has too restrictive rate limits.
        if request._num_agent_responses == 0 and not thread.activated:
            text = "Initializing :thread: ..."
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self._converter.convert(text),
                    },
                },
            ]
            await self._post_slack_message(thread, text, sender, blocks=blocks)

            # Since multiple initial permission requests may be delivered before the first agent
            # response, we mark the thread as activated after the first permission request in
            # order to avoid sending multiple initialization notifications.
            thread.activated = True

        text = f"*Execute action:*\n\n```\n{request.call}\n```\n\n"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": self._converter.convert(text),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {  # type: ignore
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Once"},
                        "action_id": "once_button",
                        "value": corr_id,
                        "style": "primary",
                    },
                    {  # type: ignore
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Session"},
                        "action_id": "session_button",
                        "value": corr_id,
                    },
                    {  # type: ignore
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Always"},
                        "action_id": "always_button",
                        "value": corr_id,
                    },
                    {  # type: ignore
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Deny"},
                        "action_id": "deny_button",
                        "value": corr_id,
                        "style": "danger",
                    },
                ],
            },
        ]

        # ----------------------------------------------------------------------------------
        # Setting the user argument causes the message to be sent as ephemeral message,
        # visible only to that user. For the moment, we send all permission requests as
        # ephemeral messages.
        #
        # Possible future improvement: only send ephemeral messages if request.as_user is
        # True. This means the user is about to execute an MCP tool with its own secrets.
        # For these permission requests, the user alone must be able to decide whether to
        # grant or deny execution. For all other permission requests, we may let any user
        # (or more restrictively, any admin) in the group decide whether to execute a tool
        # or not.
        # ----------------------------------------------------------------------------------

        await self._post_slack_message(
            thread=thread,
            text=text,
            sender=sender,
            blocks=blocks,
            user=self._resolve_slack_user_id(receiver),
        )

    async def _post_slack_message(self, thread: SlackThread, text: str, sender: str, **kwargs):
        if thread.session.agent_registry:
            emoji = await thread.session.agent_registry.get_emoji(sender)
        else:
            emoji = None

        emoji = emoji or "robot_face"

        if "user" in kwargs:
            coro = self._client.chat_postEphemeral
        else:
            coro = self._client.chat_postMessage

        await coro(
            channel=thread.channel,
            thread_ts=thread.id,
            text=text,
            username=sender,
            icon_emoji=f":{emoji}:",
            **kwargs,
        )

    async def handle_permission_response(self, ack, body):
        await ack()

        message = body.get("message") or body["container"]
        thread_id = message["thread_ts"]
        thread = self._threads.get(thread_id)

        if thread is None:
            return

        action = body["actions"][0]
        cid = action.get("value")

        if cid in thread.permission_requests:
            request = thread.permission_requests.pop(cid)
            match action["action_id"]:
                case "once_button":
                    request.grant_once()
                case "session_button":
                    request.grant_session()
                case "always_button":
                    request.grant_always()
                case "deny_button":
                    request.deny()
                case _:
                    raise ValueError(f"Unknown action: {action['action_id']}")

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

    def _register_slack_thread(self, channel_id: str, session: Session) -> SlackThread:
        session.set_gateway(self)
        session.sync()
        self._threads[session.id] = SlackThread(
            channel=channel_id,
            session=session,
        )
        return self._threads[session.id]

    def _resolve_system_user_id(self, slack_user_id: str) -> str:
        return self._slack_user_mapping.get(slack_user_id, slack_user_id)

    def _resolve_slack_user_id(self, system_user_id: str) -> str:
        return self._system_user_mapping.get(system_user_id, system_user_id)

    def _parse_slack_message(self, message: dict) -> dict:
        sender = message["user"]
        sender_resolved = self._resolve_system_user_id(sender)

        # check if there is an initial @mention in the message
        receiver, text = extract_initial_mention(message["text"])
        receiver_resolved = None if receiver is None else self._resolve_system_user_id(receiver)

        # replace all @mentions in text with resolved usernames (without @)
        text = resolve_mentions(text, self._resolve_system_user_id)

        return {
            "id": message["ts"],
            "channel": message.get("channel"),
            "sender": sender,
            "sender_resolved": sender_resolved,
            "receiver": receiver,
            "receiver_resolved": receiver_resolved,
            "text": text,
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

                try:
                    # Rate limit: https://api.slack.com/methods/conversations.replies
                    response = await self._client.conversations_replies(**params)
                except Exception as e:
                    # Log error and return. We can recover from this error later.
                    self.logger.exception(e)
                    return []

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
