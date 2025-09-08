import asyncio
import html
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import aiofiles
import aiohttp
from markdown_to_mrkdwn import SlackMarkdownConverter
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from hygroup.agent import (
    AgentActivation,
    AgentResponse,
    Attachment,
    PermissionRequest,
)
from hygroup.connect.composio import ComposioConnector
from hygroup.gateway.base import Gateway
from hygroup.session import Session, SessionManager
from hygroup.user import RequestHandler


@dataclass
class SlackThread:
    channel_id: str
    session: Session
    permission_requests: dict[str, PermissionRequest] = field(default_factory=dict)
    response_ids: dict[str, str] = field(default_factory=dict)
    response_upd: dict[str, asyncio.Task] = field(default_factory=dict)
    lock: asyncio.Lock = asyncio.Lock()

    @property
    def id(self) -> str:
        return self.session.id

    @property
    def channel_name(self) -> str | None:
        return self.session.channel

    async def handle_message(self, msg: dict):
        if self.session.contains(msg["id"]):
            return  # idempotency

        # download attachments to session store ...
        attachments = await self._download_attachments(msg)

        # and pass attachment references to handler
        await self.session.handle_gateway_message(
            text=msg["text"],
            sender=msg["sender"],
            message_id=msg["id"],
            attachments=attachments,
        )

    async def _download_attachments(self, msg: dict) -> list[Attachment] | None:
        root = self.session.root()

        files = msg.get("files")

        if not files:
            return None

        headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
        result = []

        async with aiohttp.ClientSession() as session:
            for i, file in enumerate(files):
                mimetype = file.get("mimetype", "application/octet-stream")
                filetype = file.get("filetype", "bin")
                name = file.get("name", f"unknown_{i}.{filetype}")
                url_private_download = file.get("url_private_download")

                if not url_private_download:
                    continue

                attachment_id = uuid4().hex[:8]
                filename = f"slack-attachment-{attachment_id}.{filetype}"
                target_path = root / filename

                async with session.get(url_private_download, headers=headers) as response:
                    response.raise_for_status()
                    async with aiofiles.open(target_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)

                attachment = Attachment(path=str(target_path), name=name, media_type=mimetype)
                result.append(attachment)

        return result


class SlackGateway(Gateway, RequestHandler):
    def __init__(
        self,
        session_manager: SessionManager,
        composio_connector: ComposioConnector,
        user_mapping: dict[str, str] = {},
        handle_permission_requests: bool = False,
        wip_emoji: str = "beer",
        wip_update: bool | None = None,
        wip_update_interval: float = 10.0,
        wip_update_max: int = 10,
    ):
        self.session_manager = session_manager
        self.composio_connector = composio_connector
        self.delegate_handler = session_manager.request_handler
        self.handle_permission_requests = handle_permission_requests

        self.wip_emoji = wip_emoji
        self.wip_update_interval = wip_update_interval
        self.wip_update_max = wip_update_max

        # by default, disable animation of work-in-progress messages when permission requests are
        # displayed (to the initiating user), which can be seen as a kind of progress indicator.
        self.wip_update = not handle_permission_requests if wip_update is None else wip_update

        if handle_permission_requests:
            # Gateway handles permission requests itself, delegating
            # all other requests to the original request handler.
            self.session_manager.request_handler = self

        # maps from slack user id to system user id
        self._slack_user_mapping = user_mapping
        self._slack_user_mapping[os.environ["SLACK_APP_USER_ID"]] = "system"
        # maps from system user id to slack user id
        self._system_user_mapping = {v: k for k, v in user_mapping.items()}

        self._app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
        self._client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])
        self._handler = AsyncSocketModeHandler(self._app, os.environ["SLACK_APP_TOKEN"])
        self._converter = SlackMarkdownConverter()
        self._threads: dict[str, SlackThread] = {}

        # register event handlers
        self._app.message("")(self.handle_slack_message)

        # register action listeners
        self._app.action("once_button")(self.handle_permission_response)
        self._app.action("session_button")(self.handle_permission_response)
        self._app.action("always_button")(self.handle_permission_response)
        self._app.action("deny_button")(self.handle_permission_response)

        # register command handlers
        self._app.command("/hygroup-connect")(self.handle_connect)
        self._app.command("/hygroup-command")(self.handle_command)
        self._app.command("/hygroup-agents")(self.handle_agents)

        # Suppress "unhandled request" log messages
        self.logger = logging.getLogger("slack_bolt.AsyncApp")
        self.logger.setLevel(logging.ERROR)

    @property
    def app(self) -> AsyncApp:
        return self._app

    @property
    def client(self) -> AsyncWebClient:
        return self._client

    async def handle_connect(self, ack, body, respond):
        await ack()

        user = self._resolve_system_user_id(body["user_id"])
        text = body["text"].strip()

        if text:
            block = await self._connect_toolkit_response(system_user_id=user, toolkit_name=text)
        else:
            block = await self._connection_status_response(system_user_id=user)

        await respond(blocks=[block])

    async def _connection_status_response(self, system_user_id: str) -> dict[str, Any]:
        composio_config = await self.composio_connector.load_config()
        composio_connections = await self.composio_connector.connection_status(system_user_id, composio_config)

        connection_lines = []

        connected_emoji = ":white_check_mark:"
        disconnected_emoji = ":heavy_multiplication_x:"

        for toolkit_name, connected in sorted(composio_connections.items()):
            emoji = connected_emoji if connected else disconnected_emoji
            connection_lines.append(f"{emoji} `{toolkit_name}` - {composio_config.display_name(toolkit_name)}")

        connections_text = "\n".join(connection_lines) if connection_lines else "No toolkits configured"
        response_text = f"**Composio toolkits** - {connected_emoji} connected {disconnected_emoji} disconnected\n\n{connections_text}"

        return {"type": "section", "text": {"type": "mrkdwn", "text": self._converter.convert(response_text)}}

    async def _connect_toolkit_response(self, system_user_id: str, toolkit_name: str) -> dict[str, Any]:
        composio_config = await self.composio_connector.load_config()
        toolkit_names = composio_config.toolkit_names()

        if toolkit_name not in toolkit_names:
            toolkits_text = "\n".join(f"- `{toolkit_name}`" for toolkit_name in toolkit_names)
            response_text = f"Invalid toolkit name: `{toolkit_name}`. Must be one of:\n\n{toolkits_text}"
        else:
            redirect_url = await self.composio_connector.connect_toolkit(system_user_id, toolkit_name)
            response_text = f"Follow [this link]({redirect_url}) for authorizing Composio to access your {composio_config.display_name(toolkit_name)} account."

        return {"type": "section", "text": {"type": "mrkdwn", "text": self._converter.convert(response_text)}}

    async def start(self, join: bool = True):
        if join:
            await self._handler.start_async()
        else:
            await self._handler.connect_async()

    async def handle_command(self, ack, body, respond):
        await ack()

        user = self._resolve_system_user_id(body["user_id"])
        text = body["text"].strip()

        try:
            response_text = await self._handle_command(text, user)
        except KeyError:
            response_text = ":x: Command not found."
        except ValueError as e:
            response_text = f":x: Error: {str(e)}"
        except Exception as e:
            response_text = f":x: An error occurred: {str(e)}"

        block = {"type": "section", "text": {"type": "mrkdwn", "text": self._converter.convert(response_text)}}
        await respond(blocks=[block])

    async def _handle_command(self, text: str, user: str) -> str:
        command_store = self.session_manager.command_store

        if not text or text == "list":
            command_names = await command_store.command_names(user)
            if command_names:
                command_list = "\n".join(f"• `{name}`" for name in sorted(command_names))
                response_text = f"**Saved commands:**\n{command_list}"
            else:
                response_text = "No saved commands found."
        elif text.startswith("save "):
            parts = text[5:].split(None, 1)
            if len(parts) < 2:
                response_text = ":x: Error: Please provide both a command name and command content."
            else:
                command_name, command_content = parts
                command_content = command_content.strip()
                await command_store.save_command(html.unescape(command_content), command_name, user)
                response_text = f":white_check_mark: Command `{command_name}` saved successfully."
        elif text.startswith("view "):
            command_name = text[5:].strip()
            if not command_name:
                response_text = ":x: Error: Please provide a command name."
            else:
                command_content = await command_store.load_command(command_name, user)
                response_text = f"**Command `{command_name}`:**\n```\n{command_content}\n```"
        elif text.startswith("delete "):
            command_name = text[7:].strip()
            if not command_name:
                response_text = ":x: Error: Please provide a command name."
            else:
                await command_store.delete_command(command_name, user)
                response_text = f":white_check_mark: Command `{command_name}` deleted successfully."
        elif text == "help":
            lines = [
                "**Usage:**",
                "- `/hygroup-command` or `/hygroup-command list` - List all saved commands",
                "- `/hygroup-command save <name> <command>` - Save a command",
                "- `/hygroup-command view <name>` - View a command",
                "- `/hygroup-command delete <name>` - Delete a command",
                "- `/hygroup-command help` - Show this help message",
            ]
            response_text = "\n".join(lines)
        else:
            response_text = ":x: Unknown operation. Use `/hygroup-command` without arguments to see usage."

        return response_text

    async def handle_agents(self, ack, body, respond):
        await ack()

        # Get channel ID from the command body
        channel_name = body.get("channel_name")

        # Get agent registry for that channel
        registry = self.session_manager.agent_registries.get_registry(name=channel_name)

        # Get all agent descriptions
        descriptions = registry.get_descriptions()

        # Format agent list
        agent_lines = []
        for name, description in sorted(descriptions.items()):
            emoji = registry.get_emoji(name)
            emoji_str = f":{emoji}:" if emoji else ":robot_face:"
            agent_lines.append(f"- {emoji_str} `{name}`: {description}")

        # Create response
        if agent_lines:
            agents_text = "\n".join(agent_lines)
            response_text = f"**Available agents**\n\n{agents_text}"
        else:
            response_text = "No agents are currently registered."

        # Send markdown response
        block = {"type": "section", "text": {"type": "mrkdwn", "text": self._converter.convert(response_text)}}
        await respond(blocks=[block])

    async def handle_feedback_request(self, *args, **kwargs):
        await self.delegate_handler.handle_feedback_request(*args, **kwargs)

    async def handle_agent_activation(self, activation: AgentActivation, session_id: str):
        thread = self._threads[session_id]

        if activation.message_id:
            await self._client.reactions_add(
                channel=thread.channel_id,
                timestamp=activation.message_id,
                name="eyes",
            )

        if activation.request_id:
            # Send initial work-in-progress message
            response = await self._send_wip_message(thread, activation.agent_name)
            response_id = response.data["ts"]

            thread.response_ids[activation.request_id] = response_id

            if self.wip_update:
                # Coroutine for updating the work-in-progress message
                wip_coro = self._update_wip_message(
                    thread=thread,
                    sender=activation.agent_name,
                    message_id=response_id,
                )
                thread.response_upd[activation.request_id] = asyncio.create_task(wip_coro)

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        thread = self._threads[session_id]

        if response.message_id:
            await self._client.reactions_add(
                channel=thread.channel_id,
                timestamp=response.message_id,
                name="robot_face" if response.text else "ballot_box_with_check",
            )

        if request_id := response.request_id:
            # Cancel beer timer task if it exists
            if wip_task := thread.response_upd.pop(request_id, None):
                wip_task.cancel()
                try:
                    await wip_task
                except asyncio.CancelledError:
                    pass

            if response_id := thread.response_ids.pop(request_id, None):
                await self._client.chat_delete(
                    channel=thread.channel_id,
                    thread_ts=thread.id,
                    ts=response_id,
                )

        if not response.text:
            return

        receiver_resolved = self._resolve_slack_user_id(receiver)
        receiver_resolved_formatted = f"<@{receiver_resolved}>"

        text = f"{receiver_resolved_formatted} {response.text}"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": self._converter.convert(text),
                },
            },
        ]
        await self._send_slack_message(thread, text, sender, blocks=blocks)

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str, session_id: str):  # type: ignore
        corr_id = str(uuid4())

        thread = self._threads[session_id]
        thread.permission_requests[corr_id] = request

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

        await self._send_slack_message(
            thread=thread,
            text=text,
            sender=sender,
            blocks=blocks,
            user=self._resolve_slack_user_id(receiver),
        )

    async def _update_wip_message(self, thread: SlackThread, sender: str, message_id: str):
        try:
            for i in range(2, self.wip_update_max):
                await asyncio.sleep(self.wip_update_interval)
                await self._send_wip_message(thread, sender, i, ts=message_id)
        except asyncio.CancelledError:
            # Task was cancelled, this is expected
            pass

    async def _send_wip_message(self, thread: SlackThread, sender: str, progress: int = 1, **kwargs):
        beers = f":{self.wip_emoji}:" * progress
        text = f"{beers} *brewing ...*"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": self._converter.convert(text),
                },
            },
        ]
        return await self._send_slack_message(thread, text, sender, blocks=blocks, **kwargs)

    async def _send_slack_message(self, thread: SlackThread, text: str, sender: str, **kwargs) -> AsyncSlackResponse:
        if "ts" in kwargs:
            coro = self._client.chat_update
        elif "user" in kwargs:
            coro = self._client.chat_postEphemeral
        else:
            coro = self._client.chat_postMessage

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
                    thread = await self._register_slack_thread(channel_id=msg["channel"], session=session)
                else:
                    session = self.session_manager.create_session(id=thread_id)
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
            session = self.session_manager.create_session(id=msg["id"])
            thread = await self._register_slack_thread(channel_id=msg["channel"], session=session)

            async with thread.lock:
                await thread.handle_message(msg)

    async def _register_slack_thread(self, channel_id: str, session: Session) -> SlackThread:
        channel_info = await self.client.conversations_info(channel=channel_id)
        channel_name = channel_info.data["channel"]["name"]  # noqa: F841

        session.set_gateway(self)
        session.set_channel(channel_name)
        session.sync()

        self._threads[session.id] = SlackThread(
            channel_id=channel_id,
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

        # replace all @mentions in text with resolved usernames (preserving @)
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
            resolved = self._resolve_system_user_id(user_id)
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
                    # Rate limit: https://api.slack.com/methods/conversations.replies
                    response = await self._client.conversations_replies(**params)
                except Exception as e:
                    self.logger.exception(e)
                    return []

                for message in response["messages"]:
                    # Skip messages sent by the installed app
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
