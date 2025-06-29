import json
import os
import uuid
from asyncio import Future, Queue, Task, create_task, sleep
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

import aiofiles
import aiofiles.os

from hygroup.agent import (
    Agent,
    AgentRegistry,
    AgentRequest,
    AgentResponse,
    AgentSelector,
    AgentSelectorSettings,
    ConfirmationRequest,
    FeedbackRequest,
    Message,
    PermissionRequest,
    Thread,
)
from hygroup.gateway import Gateway
from hygroup.user import PermissionStore, RequestHandler, UserRegistry
from hygroup.user.default import RichConsoleHandler


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

    async def invoke(self, request: AgentRequest, secrets: dict[str, str]):
        await self._queue.put((request, secrets))

    async def worker(self):
        async with self.agent.session_scope():
            while True:
                item = await self._queue.get()
                match item:
                    case Message():
                        self._updates.append(item)
                    case AgentRequest(sender=sender, threads=threads) as request, secrets:
                        # -------------------------------------
                        #  TODO: trace query
                        # -------------------------------------
                        async with self.agent.request_scope(config_values=secrets):
                            async for elem in self.agent.run(
                                request=request, updates=self._updates, threads=threads, stream=False
                            ):
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
        id: str | None = None,
        group: bool = True,
        manager: Optional["SessionManager"] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.group = group
        self.manager = manager or SessionManager(agent_factory=lambda: [])

        self.agent_registry = self.manager.agent_registry
        self.user_registry = self.manager.user_registry
        self.request_handler = self.manager.request_handler or RichConsoleHandler(upper_bound=1)
        self.permission_store = self.manager.permission_store

        self._gateway: Gateway | None = None
        self._agents: dict[str, SessionAgent] = {}
        self._messages: list[Message] = []

        self._sync_task: Task | None = None
        self._agent_selector: AgentSelector | None = None

        if self.agent_registry:
            self._agent_selector = AgentSelector(registry=self.agent_registry, settings=self.manager.selector_settings)

    @property
    def gateway(self) -> Gateway:
        if self._gateway is None:
            raise ValueError("Gateway not set")
        return self._gateway

    @property
    def messages(self) -> list[Message]:
        return self._messages

    async def agent_names(self) -> set[str]:
        names = set(self._agents.keys())

        if self.agent_registry:
            names |= await self.agent_registry.get_registered_names()

        return names

    def _user_authenticated(self, username: str) -> bool:
        if self.user_registry is None:
            return True
        return self.user_registry.authenticated(username)

    def _user_secrets(self, username: str) -> dict[str, str]:
        if self.user_registry is None:
            return dict(os.environ)
        return self.user_registry.get_secrets(username)

    async def _get_permission(self, tool_name: str, username: str) -> int | None:
        if self.permission_store is not None:
            return await self.permission_store.get_permission(tool_name, username, self.id)
        return None

    async def _set_permission(self, tool_name: str, username: str, response: int):
        if self.permission_store is not None:
            await self.permission_store.set_permission(tool_name, username, self.id, response)

    async def _load_agent(self, name: str):
        if self.agent_registry is None:
            return
        try:
            self.add_agent(await self.agent_registry.create_agent(name))
        except Exception:
            return

    def add_agent(self, agent: Agent):
        self._agents[agent.name] = SessionAgent(agent, self)

    def set_gateway(self, gateway: Gateway):
        self._gateway = gateway

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str):
        if permission := await self._get_permission(request.tool_name, receiver):
            request.respond(permission)
            return

        await self.request_handler.handle_permission_request(request, sender, receiver, session_id=self.id)
        permission = await request.response()

        if permission in [2, 3]:
            await self._set_permission(request.tool_name, receiver, permission)

    async def handle_feedback_request(self, request: FeedbackRequest, sender: str, receiver: str):
        await self.request_handler.handle_feedback_request(request, sender, receiver, session_id=self.id)
        await request.response()

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str):
        message = Message(sender=sender, receiver=receiver, text=response.text, handoffs=response.handoffs or None)
        await self.update(message)

        for agent, query in response.handoffs.items():
            await self.invoke(request=AgentRequest(query=query, sender=receiver), receiver=agent)

        await self.gateway.handle_agent_response(response, sender, receiver, session_id=self.id)

    async def handle_system_response(self, response: str, receiver: str):
        await self.gateway.handle_agent_response(
            response=AgentResponse(text=response, final=True),
            sender="system",
            receiver=receiver,
            session_id=self.id,
        )

    async def select(self, message: Message):
        from dataclasses import asdict

        if self._agent_selector is None:
            return

        print("Message:")
        print(json.dumps(asdict(message), indent=2))

        agent_names = await self.agent_names()

        if message.sender == "system" or message.sender in agent_names or message.receiver in agent_names:
            # we don't select an agent, just add the message to the selector's history
            await self._agent_selector.add(message)
            return

        selection = await self._agent_selector.run(message)

        print("Selection:")
        print(json.dumps(selection.model_dump(), indent=2))

        if selection.agent_name in agent_names and selection.query:
            confirmation_request = ConfirmationRequest(query=selection.query, ftr=Future())
            await self.request_handler.handle_confirmation_request(
                confirmation_request,
                sender=selection.agent_name,
                receiver=message.sender,
                session_id=self.id,
            )

            # blocks until confirmation_request.respond() is called
            confirmation_response = await confirmation_request.response()
            if not confirmation_response.confirmed:
                return

            agent_request = AgentRequest(query=selection.query, sender=message.sender)
            await self.invoke(agent_request, selection.agent_name)

    async def update(self, message: Message):
        self._messages.append(message)

        if self.group:
            for agent_name, agent in self._agents.items():
                if agent_name not in [message.sender, message.receiver]:
                    await agent.update(message)

        create_task(self.select(message))

    async def invoke(self, request: AgentRequest, receiver: str):
        if not self._user_authenticated(request.sender):
            return await self.handle_system_response(
                response=f'User "{request.sender}" is not authenticated',
                receiver=request.sender,
            )

        if receiver not in self._agents:
            await self._load_agent(receiver)

        if receiver in self._agents:
            # get secrets of authenticated sender
            secrets = self._user_secrets(request.sender)
            # invoke receiver agent with request
            await self._agents[receiver].invoke(request, secrets)
            message = Message(
                sender=request.sender,
                receiver=receiver,
                text=request.query,
                id=request.id,
            )
            # notify others about this request
            await self.update(message)
        else:
            # make sure the gateway doesn't block us
            create_task(
                self.handle_system_response(
                    response=f'Agent "{receiver}" does not exist',
                    receiver=request.sender,
                )
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
        if self._agent_selector:
            state_dict["selector"] = self._agent_selector.get_state()
        await self.manager.save_session_state(self.id, state_dict)

    async def load(self):
        state_dict = await self.manager.load_session_state(self.id)

        # restore agent states
        for name, state in state_dict["agents"].items():
            if name in self._agents:
                self._agents[name].set_state(state)

        # restore selector agent state
        if self._agent_selector and "selector" in state_dict:
            self._agent_selector.set_state(state_dict["selector"])

        # restore thread messages
        self._messages = [Message(**message) for message in state_dict["messages"]]


AgentFactory = Callable[[], list[Agent]]


class SessionManager:
    def __init__(
        self,
        agent_factory: AgentFactory,
        agent_registry: AgentRegistry | None = None,
        user_registry: UserRegistry | None = None,
        permission_store: PermissionStore | None = None,
        request_handler: RequestHandler | None = None,
        selector_settings: AgentSelectorSettings | None = None,
        root_dir: Path = Path(".data", "sessions"),
    ):
        self.agent_factory = agent_factory
        self.agent_registry = agent_registry
        self.user_registry = user_registry
        self.permission_store = permission_store
        self.request_handler = request_handler
        self.selector_settings = selector_settings

        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, id: str | None = None, agent_factory: AgentFactory | None = None) -> Session:
        session = Session(id=id, manager=self)
        factory = agent_factory or self.agent_factory

        for agent in factory():
            session.add_agent(agent)

        return session

    async def load_session(self, id: str, agent_factory: AgentFactory | None = None) -> Session | None:
        if not await self.session_saved(id):
            return None
        session = self.create_session(id, agent_factory)
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
