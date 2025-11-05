import logging
import re
from asyncio import Future, Queue, Task, create_task
from pathlib import Path
from typing import AsyncIterator

from group_genie.agent import AgentFactory, Approval, Decision
from group_genie.datastore import DataStore
from group_genie.message import Attachment, Message, Thread
from group_genie.reasoner import GroupReasonerFactory
from group_genie.session import Execution, GroupSession

from hygroup.agent import PermissionRequest
from hygroup.channel import RequestHandler
from hygroup.gateway import (
    AgentActivation,
    AgentResponse,
    AgentUpdate,
    Gateway,
    MessageAck,
    MessageIgnore,
)
from hygroup.user.secrets import SecretsStore
from hygroup.user.settings import CommandNotFoundError, SettingsStore

logger = logging.getLogger(__name__)


class Session:
    def __init__(
        self,
        id: str,
        gateway: Gateway,
        group_reasoner_factory: GroupReasonerFactory,
        agent_factory: AgentFactory,
        session_factory: "SessionFactory",
    ):
        self.gateway = gateway
        self.session_factory = session_factory
        self.session = GroupSession(
            id=id,
            group_reasoner_factory=group_reasoner_factory,
            agent_factory=agent_factory,
            data_store=session_factory.data_store,
            preferences_source=session_factory.settings_store,
        )

        self._handler_queue: Queue = Queue()
        self._handler_task: Task = create_task(self._handler_worker(self._handler_queue))

    @property
    def id(self) -> str:
        return self.session.id

    @property
    def settings_store(self) -> SettingsStore:
        return self.session_factory.settings_store

    @property
    def agent_factory(self) -> AgentFactory:
        return self.session.agent_factory

    async def request_ids(self) -> set[str]:
        return await self.session.request_ids()

    async def handle(self, text: str, sender: str, attachments: list[Attachment] = [], request_id: str | None = None):
        receiver, text = self._initial_mention(text)
        text = await self._expand_command(text, sender)

        thread_refs = self._thread_references(text)
        threads = await self.session_factory.load_threads(thread_refs)

        message = Message(
            content=text,
            sender=sender,
            receiver=receiver,
            threads=threads,
            attachments=attachments,
            request_id=request_id,
        )

        await self.send_message_ack(receiver=sender, request_id=request_id)
        execution = self.session.handle(message)
        create_task(self._complete(execution, request=message))

    async def send_message_ack(self, receiver: str, request_id: str | None = None):
        notification = MessageAck(
            sender="system",
            receiver=receiver,
            session_id=self.id,
            request_id=request_id,
        )
        coro = self.gateway.handle_message_ack(notification)
        await self._handler_queue.put(coro)

    async def send_message_ignore(self, receiver: str, request_id: str | None = None):
        notification = MessageIgnore(
            sender="system",
            receiver=receiver,
            session_id=self.id,
            request_id=request_id,
        )
        coro = self.gateway.handle_message_ignore(notification)
        await self._handler_queue.put(coro)

    async def send_agent_activation(self, receiver: str, request_id: str | None = None):
        notification = AgentActivation(
            sender="system",
            receiver=receiver,
            session_id=self.id,
            request_id=request_id,
        )
        coro = self.gateway.handle_agent_activation(notification)
        await self._handler_queue.put(coro)

    async def send_agent_update(self, approval: Approval, receiver: str, request_id: str | None = None):
        notification = AgentUpdate(
            sender=approval.sender,
            receiver=receiver,
            session_id=self.id,
            request_id=request_id,
            tool_name=approval.tool_name,
            tool_kwargs=approval.tool_kwargs,
        )
        coro = self.gateway.handle_agent_update(notification)
        await self._handler_queue.put(coro)

    async def send_agent_response(self, message: Message):
        notification = AgentResponse(
            sender=message.sender,
            receiver=message.receiver,
            session_id=self.id,
            request_id=message.request_id,
            text=message.content,
            final=True,
        )
        coro = self.gateway.handle_agent_response(notification)
        await self._handler_queue.put(coro)

    async def send_permission_request(self, approval: Approval, receiver: str):
        if await self.session_factory.settings_store.get_permission(receiver, approval.tool_name, self.id):
            approval.approve()
            return

        request = PermissionRequest(
            tool_name=approval.tool_name,
            tool_args=approval.tool_args,
            tool_kwargs=approval.tool_kwargs,
            ftr=Future[int](),
        )
        coro = self.session_factory.request_handler.handle_permission_request(
            request, sender=approval.sender, receiver=receiver, session_id=self.id
        )
        await self._handler_queue.put(coro)

        permission = await request.response()
        if permission == 0:
            approval.deny()
        else:
            approval.approve()

        if permission == 2:
            await self.session_factory.settings_store.set_permission(receiver, request.tool_name, self.id)
        elif permission == 3:
            await self.session_factory.settings_store.set_permission(receiver, request.tool_name, None)

    async def _complete(self, execution: Execution, request: Message):
        try:
            await self._complete_stream(execution.stream(), request)
        except Exception as e:
            logger.exception(e)
            response = Message(
                content=f"Agent execution error: {e}",
                sender="system",
                receiver=request.sender,
                request_id=request.request_id,
            )
            await self.send_agent_response(
                message=response,
            )

    async def _complete_stream(self, stream: AsyncIterator[Decision | Approval | Message], request: Message):
        async for elem in stream:
            match elem:
                case Decision.IGNORE:
                    await self.send_message_ignore(
                        receiver=request.sender,
                        request_id=request.request_id,
                    )
                case Decision.DELEGATE:
                    await self.send_agent_activation(
                        receiver=request.sender,
                        request_id=request.request_id,
                    )
                case Approval():
                    await self.send_permission_request(
                        approval=elem,
                        receiver=request.sender,
                    )
                    await self.send_agent_update(
                        approval=elem,
                        receiver=request.sender,
                        request_id=request.request_id,
                    )
                case Message():
                    await self.send_agent_response(
                        message=elem,
                    )

    async def _expand_command(self, query: str, sender: str) -> str:
        if not query or not query.startswith("%"):
            return query

        # Extract potential command name and arguments
        parts = query[1:].split(None, 1)
        if not parts:
            return query

        command_name = parts[0]
        arguments = parts[1] if len(parts) > 1 else ""

        # Check if it matches the command name pattern
        # TODO: can be removed
        if not re.match(r"^[a-zA-Z0-9_-]+$", command_name):
            return query

        command_content = await self.session_factory.settings_store.get_command(sender, command_name)

        if command_content is None:
            raise CommandNotFoundError(command_name)

        # Handle {ARGUMENTS} placeholder
        if "{ARGUMENTS}" in command_content:
            return command_content.replace("{ARGUMENTS}", arguments)
        elif arguments:
            # Append arguments after a space if no placeholder
            return f"{command_content} {arguments}"
        else:
            return command_content

    @staticmethod
    def _initial_mention(text: str):
        if not text:
            return None, text

        # Match '@name' at the beginning, with optional surrounding whitespace.
        match = re.match(r"^\s*@([/\w-]+)\s*([\s\S]*)", text)

        if match:
            # return mention and remaining text
            return match.group(1), match.group(2)

        return None, text

    @staticmethod
    def _thread_references(text: str) -> list[str]:
        return re.findall(r"thread:([a-zA-Z0-9.-]+)", text)

    async def _handler_worker(self, queue: Queue):
        while True:
            coro = await queue.get()
            try:
                await coro
            except Exception as e:
                logger.exception(e)


class SessionFactory:
    def __init__(
        self,
        settings_store: SettingsStore,
        secrets_store: SecretsStore,
        request_handler: RequestHandler,
        group_reasoner_factory: GroupReasonerFactory,
        agent_factory: AgentFactory,
        group_reasoner_factories: dict[str, GroupReasonerFactory] = {},
        agent_factories: dict[str, AgentFactory] = {},
        root_path: Path = Path(".data", "sessions"),
    ):
        self.settings_store = settings_store
        self.secrets_store = secrets_store
        self.request_handler = request_handler
        self.group_reasoner_factory = group_reasoner_factory
        self.group_reasoner_factories = group_reasoner_factories
        self.agent_factory = agent_factory
        self.agent_factories = agent_factories
        self.data_store = DataStore(root_path=root_path)

    async def load_threads(self, session_ids: list[str]) -> list[Thread]:
        threads = []
        for session_id in session_ids:
            if thread := await self.load_thread(session_id):
                threads.append(thread)
        return threads

    async def load_thread(self, session_id: str) -> Thread | None:
        async with self.data_store.narrow(session_id) as session_store:
            if messages := await GroupSession.load_messages(session_store):
                return Thread(id=session_id, messages=messages)
        return None

    def get_agent_factory(self, channel_name: str | None = None) -> AgentFactory:
        if channel_name is None:
            return self.agent_factory
        else:
            return self.agent_factories.get(channel_name, self.agent_factory)

    def get_group_reasoner_factory(self, channel_name: str | None = None) -> GroupReasonerFactory:
        if channel_name is None:
            return self.group_reasoner_factory
        else:
            return self.group_reasoner_factories.get(channel_name, self.group_reasoner_factory)

    def create_session(self, id: str, gateway: Gateway, channel_name: str | None = None) -> Session:
        return Session(
            id=id,
            gateway=gateway,
            agent_factory=self.get_agent_factory(channel_name),
            group_reasoner_factory=self.get_group_reasoner_factory(channel_name),
            session_factory=self,
        )
