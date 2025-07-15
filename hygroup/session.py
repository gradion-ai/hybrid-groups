import json
import logging
import re
import uuid
from asyncio import Future, Queue, Task, create_task, sleep
from dataclasses import asdict
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

from hygroup.agent import (
    Agent,
    AgentRegistry,
    AgentRequest,
    AgentResponse,
    AgentSelectionConfirmationRequest,
    AgentSelector,
    AgentSelectorSettings,
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

    async def invoke(self, request: AgentRequest, secrets: dict[str, str] | None = None):
        await self._queue.put((request, secrets))

    async def worker(self):
        async with self.agent.session_scope():
            while True:
                item = await self._queue.get()
                match item:
                    case Message():
                        self._updates.append(item)
                    case AgentRequest(sender=sender) as request, secrets:
                        # -------------------------------------
                        #  TODO: trace query
                        # -------------------------------------
                        async with self.agent.request_scope(secrets=secrets):
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
                                        await self.session.handle_agent_response(
                                            response=elem, sender=self.agent.name, receiver=sender
                                        )

                            # agent now has notifications part of
                            # its history, so we can clear it
                            self._updates = []


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
        self.selector_settings: AgentSelectorSettings | None = self.manager.selector_settings

        self._agents: dict[str, SessionAgent] = {}
        self._messages: list[Message] = []
        self._sync_task: Task | None = None

        self._gateway_queue: Queue = Queue()
        self._gateway_task: Task = create_task(self._gateway_worker())
        self._gateway: Gateway | None = None

        self._request_handler_queue: Queue = Queue()
        self._request_handler_task: Task = create_task(self._request_handler_worker())
        self._request_handler = self.manager.request_handler

        self._selector_queue: Queue = Queue()
        self._selector_task: Task = create_task(self._selector_worker())
        self._selector: AgentSelector = AgentSelector(
            registry=self.agent_registry,
            settings=self.selector_settings,
        )

    async def _gateway_worker(self):
        # for sequential (but not atomic) execution of gateway methods
        await self._worker(self._gateway_queue)

    async def _request_handler_worker(self):
        # for sequential (but not atomic) execution of request handler methods
        await self._worker(self._request_handler_queue)

    async def _selector_worker(self):
        # for sequential (but not atomic) execution of select()
        await self._worker(self._selector_queue)

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
        message = Message(sender=sender, receiver=receiver, text=response.text, handoffs=response.handoffs or None)

        # If an agent response contains thread references, we don't load the threads
        # because the corresponding request or a message that triggered the request
        # already contains the loaded threads.
        await self.update(message, reference=False)

        for agent, query in response.handoffs.items():
            await self.invoke(request=AgentRequest(query=query, sender=receiver), receiver=agent)

        coro = self.gateway.handle_agent_response(response, sender, receiver, session_id=self.id)
        await self._gateway_queue.put(coro)

    async def handle_system_response(self, response: str, receiver: str):
        coro = self.gateway.handle_agent_response(
            response=AgentResponse(text=response, final=True),
            sender="system",
            receiver=receiver,
            session_id=self.id,
        )
        await self._gateway_queue.put(coro)

    async def select(self, message: Message):
        # agent names currently available in registry
        agent_names = await self.agent_names()

        if message.sender == "system" or message.sender in agent_names or message.receiver in agent_names:
            # we don't select an agent, just add the message to the selector's history
            await self._selector.add(message)
            return

        if message.id:
            coro = self.gateway.handle_agent_activation(
                agent_name="selector", message_id=message.id, session_id=self.id
            )
            await self._gateway_queue.put(coro)

        selection_result = await self._selector.run(message)
        selection = selection_result.selection

        if selection.agent_name in agent_names or selection.agent_name is None:
            confirmation_request = AgentSelectionConfirmationRequest(
                selection_result=selection_result,
                ftr=Future(),
            )
            coro = self._request_handler.handle_confirmation_request(
                confirmation_request,
                sender="selector",
                receiver=message.sender,
                session_id=self.id,
            )
            await self._request_handler_queue.put(coro)

            # blocks until confirmation_request.respond() is called
            confirmation_response = await confirmation_request.response()

            if not confirmation_response.confirmed or selection.agent_name is None or selection.query is None:
                if message.id:
                    coro = self.gateway.handle_agent_activation(
                        agent_name=None,
                        message_id=message.id,
                        session_id=self.id,
                    )
                    await self._gateway_queue.put(coro)
                return

            agent_request = AgentRequest(query=selection.query, sender=message.sender, id=message.id)
            await self.invoke(agent_request, selection.agent_name, selected=True)

    async def update(self, message: Message, reference: bool = True):
        if not message.threads and reference:
            # Load any threads referenced with `thread:...` in the message text.
            message.threads = await self._load_referenced_threads(message.text)

        # Add message to this session's message history. These are
        # are the messages that users see on the platforms integrated
        # by gateways.
        self._messages.append(message)

        if self.group:
            for agent_name, agent in self._agents.items():
                if agent_name not in [message.sender, message.receiver]:
                    await agent.update(message)

        coro = self.select(message)
        await self._selector_queue.put(coro)

    async def invoke(self, request: AgentRequest, receiver: str, selected: bool = False):
        if receiver not in self._agents:
            try:
                await self.load_agent(receiver)
            except ValueError:
                return await self.handle_system_response(
                    response=f'Agent "{receiver}" not registered',
                    receiver=request.sender,
                )

        if receiver in self._agents:
            if request.id:
                coro = self.gateway.handle_agent_activation(
                    agent_name=receiver,
                    message_id=request.id,
                    session_id=self.id,
                )
                await self._gateway_queue.put(coro)

            # get secrets of authenticated sender
            secrets = self.user_registry.get_secrets(request.sender)

            if not selected:
                # Load referenced threads only if this invocation wasn't an agent selection.
                # If it was a selection, others have already been updated with the message that
                # contains the loaded threads.
                request.threads = await self._load_referenced_threads(request.query)

            # invoke receiver agent with request
            await self._agents[receiver].invoke(request, secrets)

            if not selected:
                # Only update others in the group if this invocation wasn't an agent selection.
                # If it was a selection, others have already been updated with the message that
                # triggered the selection.
                message = Message(
                    sender=request.sender,
                    receiver=receiver,
                    text=request.query,
                    threads=request.threads,
                    id=request.id,
                )
                await self.update(message)
        else:
            await self.handle_system_response(
                response=f'Agent "{receiver}" does not exist',
                receiver=request.sender,
            )

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
        state_dict["selector"] = self._selector.get_state()
        await self.manager.save_session_state(self.id, state_dict)

    async def load(self):
        state_dict = await self.manager.load_session_state(self.id)

        # restore agent states
        for name, state in state_dict["agents"].items():
            if name in self._agents:
                self._agents[name].set_state(state)

        # restore selector agent state
        self._selector.set_state(state_dict["selector"])

        # restore thread messages
        self._messages = [Message(**message) for message in state_dict["messages"]]


class SessionManager:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        user_registry: UserRegistry,
        permission_store: PermissionStore,
        request_handler: RequestHandler,
        selector_settings: AgentSelectorSettings | None = None,
        root_dir: Path = Path(".data", "sessions"),
    ):
        self.agent_registry = agent_registry
        self.user_registry = user_registry
        self.permission_store = permission_store
        self.request_handler = request_handler
        self.selector_settings = selector_settings

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
