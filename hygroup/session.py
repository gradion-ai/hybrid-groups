import logging
import re
from asyncio import Future, Queue, Task, create_task
from pathlib import Path

from hylabs.agent import AgentRegistry, Approval, SystemAgentExecution
from hylabs.datastore import DataStore
from hylabs.message import Attachment, Message, Thread
from hylabs.session import GroupSession

from hygroup.agent import AgentActivation, AgentResponse, PermissionRequest
from hygroup.channel import RequestHandler
from hygroup.gateway import Gateway
from hygroup.user.secrets import SecretsStore
from hygroup.user.settings import SettingsStore

logger = logging.getLogger(__name__)


class Session:
    def __init__(self, id: str, gateway: Gateway, agent_registry: AgentRegistry, session_factory: "SessionFactory"):
        self.session = GroupSession(id, agent_registry, session_factory.secrets_store, session_factory.data_store)
        self.gateway = gateway
        self.session_factory = session_factory

        self._handler_queue: Queue = Queue()
        self._handler_task: Task = create_task(self._handler_worker(self._handler_queue))

    @property
    def id(self) -> str:
        return self.session.id

    @property
    def settings_store(self) -> SettingsStore:
        return self.session_factory.settings_store

    @property
    def agent_registry(self) -> AgentRegistry:
        return self.session.agent_registry

    async def request_ids(self) -> set[str]:
        return await self.session.request_ids()

    async def handle(self, text: str, sender: str, attachments: list[Attachment] = [], request_id: str | None = None):
        receiver, text = self._initial_mention(text)
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
        preferences = await self.settings_store.get_preferences(message.sender)
        execution = self.session.handle(message, preferences=preferences)

        # complete system agent execution in a separate task
        create_task(self._complete(message.request_id, execution))

    async def handle_agent_activation(self, request_id: str, session_id: str):
        agent_activation = AgentActivation(agent_name="system", request_id=request_id)
        coro = self.gateway.handle_agent_activation(agent_activation, session_id)
        await self._handler_queue.put(coro)

    async def handle_agent_response(self, message: Message, session_id: str):
        agent_response = AgentResponse(text=message.content, request_id=message.request_id, final=True)
        coro = self.gateway.handle_agent_response(agent_response, message.sender, message.receiver, session_id)
        await self._handler_queue.put(coro)

    async def handle_permission_request(self, approval: Approval, sender: str, receiver: str, session_id: str):
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
            request, sender=sender, receiver=receiver, session_id=session_id
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

    async def _complete(self, request_id: str, execution: SystemAgentExecution):
        await self.handle_agent_activation(request_id=request_id, session_id=self.session.id)
        async for elem in execution.stream():
            match elem:
                case Approval():
                    await self.handle_permission_request(
                        approval=elem,
                        sender=elem.sender,
                        receiver=elem.receiver,
                        session_id=self.session.id,
                    )
                case Message():
                    await self.handle_agent_response(
                        message=elem,
                        session_id=self.session.id,
                    )

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
        agent_registry: AgentRegistry,
        agent_registries: dict[str, AgentRegistry] = {},
        root_path: Path = Path(".data", "sessions"),
    ):
        self.settings_store = settings_store
        self.secrets_store = secrets_store
        self.request_handler = request_handler
        self.agent_registry = agent_registry
        self.agent_registries = agent_registries
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

    def get_agent_registry(self, channel_name: str | None = None) -> AgentRegistry:
        if channel_name is None:
            return self.agent_registry
        else:
            return self.agent_registries.get(channel_name, self.agent_registry)

    def create_session(self, id: str, gateway: Gateway, channel_name: str | None = None) -> Session:
        return Session(id, gateway, self.get_agent_registry(channel_name), session_factory=self)
