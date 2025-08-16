import json
import logging
import re
import uuid
from asyncio import Queue, Task, create_task, sleep
from contextvars import ContextVar
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

from hygroup.agent import (
    Agent,
    AgentActivation,
    AgentRegistry,
    AgentRequest,
    AgentResponse,
    FeedbackRequest,
    Message,
    PermissionRequest,
    Thread,
)
from hygroup.gateway import Gateway
from hygroup.user import PermissionStore, RequestHandler, UserRegistry

logger = logging.getLogger(__name__)


class SessionAgent:
    def __init__(self, agent: Agent, session: "Session"):
        self.agent = agent
        self.session = session
        self._updates: list[Message] = session.messages.copy()
        self._queue: Queue = Queue()
        self._task = create_task(self.worker())

    def get_state(self) -> dict[str, Any]:
        return {
            "updates": [asdict(update) for update in self._updates],
            "history": self.agent.get_state(),
        }

    def set_state(self, state: dict[str, Any]):
        self._updates = [Message(**update) for update in state["updates"]]
        self.agent.set_state(state["history"])

    async def update(self, message: Message):
        await self._queue.put(message)

    async def invoke(
        self, request: AgentRequest, secrets: dict[str, str] | None = None, response_channel: Queue | None = None
    ):
        await self._queue.put((request, secrets, response_channel))

    async def worker(self):
        async with self.agent.session_scope():
            while True:
                item = await self._queue.get()
                match item:
                    case Message():
                        self._updates.append(item)
                    case AgentRequest(
                        sender=sender, id=request_id, message_id=message_id
                    ) as request, secrets, response_channel:
                        # needed by agent invocation tools
                        # -------------------------------------
                        #  TODO: revise
                        # -------------------------------------
                        self.session._secrets_var.set(secrets)

                        # -------------------------------------
                        #  TODO: trace query
                        # -------------------------------------
                        async with self.agent.request_scope(secrets=secrets):
                            try:
                                async for elem in self.agent.run(request=request, updates=self._updates, stream=False):
                                    match elem:
                                        case PermissionRequest():
                                            # -------------------------------------
                                            #  TODO: trace permission request
                                            # -------------------------------------
                                            await self.session.handle_permission_request(
                                                request=elem, sender=self.agent.name, receiver=sender
                                            )
                                        case FeedbackRequest():
                                            # -------------------------------------
                                            #  TODO: trace feedback request
                                            # -------------------------------------
                                            await self.session.handle_feedback_request(
                                                request=elem, sender=self.agent.name, receiver=sender
                                            )
                                        case AgentResponse():
                                            # -------------------------------------
                                            #  TODO: trace result
                                            # -------------------------------------
                                            response = replace(elem, request_id=request_id, message_id=message_id)
                                            if response_channel is not None:
                                                await response_channel.put(response)
                                            else:
                                                await self.session.handle_agent_response(
                                                    response=response, sender=self.agent.name, receiver=sender
                                                )
                                # agent now has notifications part of
                                # its history, so we can clear it
                                self._updates = []
                            except Exception as e:
                                logger.exception(e)
                                response = AgentResponse(
                                    text=f"Execution of agent '{self.agent.name}' failed.",
                                    request_id=request_id,
                                )
                                if response_channel is not None:
                                    await response_channel.put(response)
                                else:
                                    await self.session.handle_system_response(
                                        response=response,
                                        receiver=sender,
                                    )


class Session:
    def __init__(
        self,
        manager: "SessionManager",
        id: str | None = None,
        group: bool = True,
    ):
        self.id = id or str(uuid.uuid4())
        self.group = group
        self.manager = manager

        self.agent_registry: AgentRegistry = self.manager.agent_registry
        self.user_registry: UserRegistry = self.manager.user_registry
        self.permission_store: PermissionStore = self.manager.permission_store

        self._agents: dict[str, SessionAgent] = {}
        self._messages: list[Message] = []
        self._sync_task: Task | None = None

        self._gateway_queue: Queue = Queue()
        self._gateway_task: Task = create_task(self._gateway_worker())
        self._gateway: Gateway | None = None

        self._request_handler_queue: Queue = Queue()
        self._request_handler_task: Task = create_task(self._request_handler_worker())
        self._request_handler = self.manager.request_handler

        from hygroup.user.default.preferences import DefaultPreferenceStore

        self.preferences_store = DefaultPreferenceStore()

        from hygroup.agent.system.agent import SystemAgent, system_agent_settings

        system_agent = SystemAgent(settings=system_agent_settings)
        system_agent.tool(requires_permission=True)(self.invoke_agent)
        system_agent.tool(requires_permission=True)(self.get_user_preferences)
        system_agent.tool(requires_permission=True)(self.agent_registry.get_registered_agents)
        self.add_agent(system_agent)

        self._secrets_var = ContextVar[dict[str, str]]("secrets")

    async def _gateway_worker(self):
        # for sequential (but not atomic) execution of gateway methods
        await self._worker(self._gateway_queue)

    async def _request_handler_worker(self):
        # for sequential (but not atomic) execution of request handler methods
        await self._worker(self._request_handler_queue)

    async def _worker(self, queue: Queue):
        while True:
            coro = await queue.get()
            try:
                await coro
            except Exception as e:
                logger.exception(e)

    @property
    def gateway(self) -> Gateway:
        if self._gateway is None:
            raise ValueError("Gateway not set")
        return self._gateway

    @property
    def messages(self) -> list[Message]:
        return self._messages

    def set_gateway(self, gateway: Gateway):
        self._gateway = gateway

    def add_agent(self, agent: Agent):
        self._agents[agent.name] = SessionAgent(agent, self)

    async def load_agent(self, name: str):
        self.add_agent(await self.agent_registry.create_agent(name))

    async def agent_names(self) -> set[str]:
        names = set(self._agents.keys())
        names |= await self.agent_registry.get_registered_names()
        return names

    async def _num_agent_responses(self) -> int:
        agent_names = await self.agent_names()
        agent_responses = [m for m in self._messages if m.sender in agent_names or m.sender == "system"]
        return len(agent_responses)

    async def _load_referenced_threads(self, text: str) -> list[Thread]:
        refs = self.extract_thread_references(text)
        return await self.manager.load_threads(refs)

    @staticmethod
    def extract_thread_references(text: str) -> list[str]:
        pattern = r"thread:([a-zA-Z0-9.-]+)"
        return re.findall(pattern, text)

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str):
        if permission := await self.permission_store.get_permission(request.tool_name, receiver, self.id):
            request.respond(permission)
            return

        # snapshot of the number of agent responses in session
        # (relevant only for Slack gateway at the moment)
        request._num_agent_responses = await self._num_agent_responses()

        coro = self._request_handler.handle_permission_request(request, sender, receiver, session_id=self.id)
        await self._request_handler_queue.put(coro)

        permission = await request.response()

        if permission in [2, 3]:
            await self.permission_store.set_permission(request.tool_name, receiver, self.id, permission)

    async def handle_feedback_request(self, request: FeedbackRequest, sender: str, receiver: str):
        coro = self._request_handler.handle_feedback_request(request, sender, receiver, session_id=self.id)
        await self._request_handler_queue.put(coro)
        await request.response()

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str):
        if response.text:
            message = Message(sender=sender, receiver=receiver, text=response.text)
            await self.update_agents(message, exclude=sender)

        coro = self.gateway.handle_agent_response(response, sender, receiver, session_id=self.id)
        await self._gateway_queue.put(coro)

    async def handle_system_response(self, response: AgentResponse, receiver: str):
        await self.handle_agent_response(
            response=response,
            sender="system",
            receiver=receiver,
        )

    async def process_message(self, message: Message):
        if not message.threads:
            # Load any threads referenced with `thread:...` in the message text.
            message.threads = await self._load_referenced_threads(message.text)

        request = AgentRequest(
            query=message.text,
            sender=message.sender,
            threads=message.threads,
            message_id=message.id,
        )

        if message.receiver in await self.agent_names():
            await self.update_agents(message, exclude=message.receiver)
            await self.invoke_receiver(request, message.receiver)
        else:
            await self.update_agents(message, exclude="system")
            await self.invoke_receiver(request, "system")
            # TODO: process message as an inbound message
            ...

    async def invoke_receiver(self, request: AgentRequest, receiver: str):
        # -------------------------------------
        #  FIXME: run this if block atomically
        # -------------------------------------
        if receiver not in self._agents:
            try:
                await self.load_agent(receiver)
            except ValueError:
                response = AgentResponse(
                    text=f'Agent "{receiver}" not registered',
                    request_id=request.id,
                )
                return await self.handle_system_response(
                    response=response,
                    receiver=request.sender,
                )

        activation = AgentActivation(
            agent_name=receiver,
            message_id=request.message_id,
            request_id=request.id,
        )
        coro = self.gateway.handle_agent_activation(
            activation=activation,
            session_id=self.id,
        )
        await self._gateway_queue.put(coro)

        # get secrets of authenticated sender
        secrets = self.user_registry.get_secrets(request.sender)

        # invoke receiver agent with request
        await self._agents[receiver].invoke(request, secrets)

    async def update_agents(self, message: Message, exclude: str):
        # Add message to this session's message history. These are
        # are the messages that users see on the platforms integrated
        # by gateways.
        self._messages.append(message)

        for agent_name, agent in self._agents.items():
            if agent_name != exclude:
                await agent.update(message)

    # -------------------------------------
    #  Special tool for system agent
    # -------------------------------------
    async def get_user_preferences(self, username: str):
        preferences = await self.preferences_store.get_preferences(username)
        preferences = preferences or "n/a"
        return f"User preferences for {username}:\n{preferences}"

    # -------------------------------------
    #  Special tool for system agent
    # -------------------------------------
    async def invoke_agent(self, agent_name: str, query: str) -> str:
        """
        Invoke an agent identified by agent_name with the given query and return its response.
        """
        # -------------------------------------
        #  FIXME: run this if block atomically
        # -------------------------------------
        if agent_name not in self._agents:
            try:
                await self.load_agent(agent_name)
            except ValueError:
                return f'Agent "{agent_name}" not registered'

        request = AgentRequest(query=query, sender="system")
        secrets = self._secrets_var.get()

        response_channel: Queue = Queue()
        await self._agents[agent_name].invoke(request, secrets, response_channel)
        response = await response_channel.get()

        return response.text

    def contains(self, id: str) -> bool:
        return any(message.id == id for message in self._messages)

    def sync(self, interval: float = 3.0):
        if self._sync_task is None:
            self._sync_task = create_task(self._sync(interval))

    async def _sync(self, interval: float):
        if not await self.manager.session_saved(self.id):
            await self.save()
        while True:
            await sleep(interval)
            await self.save()

    async def save(self):
        state_dict = {
            "messages": [asdict(message) for message in self._messages],
            "agents": {name: adapter.get_state() for name, adapter in self._agents.items()},
        }
        await self.manager.save_session_state(self.id, state_dict)

    async def load(self):
        state_dict = await self.manager.load_session_state(self.id)

        # restore agent states
        for name, state in state_dict["agents"].items():
            if name in self._agents:
                self._agents[name].set_state(state)

        # restore thread messages
        self._messages = [Message(**message) for message in state_dict["messages"]]


class SessionManager:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        user_registry: UserRegistry,
        permission_store: PermissionStore,
        request_handler: RequestHandler,
        root_dir: Path = Path(".data", "sessions"),
    ):
        self.agent_registry = agent_registry
        self.user_registry = user_registry
        self.permission_store = permission_store
        self.request_handler = request_handler

        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, id: str | None = None) -> Session:
        return Session(manager=self, id=id)

    async def load_session(self, id: str) -> Session | None:
        if not await self.session_saved(id):
            return None
        session = self.create_session(id)
        await session.load()
        return session

    def session_path(self, id: str) -> Path:
        return self.root_dir / f"{id}.json"

    async def session_saved(self, id: str) -> bool:
        return await aiofiles.os.path.exists(str(self.session_path(id)))

    async def save_session_state(self, id: str, state: dict[str, Any]):
        async with aiofiles.open(self.session_path(id), "w") as f:
            await f.write(json.dumps(state, indent=2))

    async def load_session_state(self, id: str) -> dict[str, Any]:
        async with aiofiles.open(self.session_path(id), "r") as f:
            state_str = await f.read()
        return json.loads(state_str)

    async def load_thread(self, id: str) -> Thread:
        state = await self.load_session_state(id)
        messages = [Message(**message) for message in state["messages"]]
        return Thread(session_id=id, messages=messages)

    async def load_threads(self, session_ids: list[str]) -> list[Thread]:
        threads = []
        for session_id in session_ids:
            if not await self.session_saved(session_id):
                continue
            threads.append(await self.load_thread(session_id))
        return threads
