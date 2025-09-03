import json
import logging
import re
from asyncio import Queue, Task, create_task, sleep
from contextvars import ContextVar
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable

import aiofiles
import aiofiles.os

from hygroup.agent import (
    Agent,
    AgentActivation,
    AgentRequest,
    AgentResponse,
    Attachment,
    FeedbackRequest,
    Message,
    PermissionRequest,
    Thread,
)
from hygroup.agent.registry import AgentRegistries
from hygroup.connect import ComposioConfig
from hygroup.gateway import Gateway
from hygroup.user import CommandStore, PermissionStore, RequestHandler, UserRegistry
from hygroup.user.default import DefaultPreferenceStore

logger = logging.getLogger(__name__)


class SessionAgent:
    def __init__(self, agent: Agent, session: "Session"):
        self.agent = agent
        self.session = session

        # ------------------------------------------------------------
        #  TODO: Consider making this configurable. Subagents don't
        #        necessarily need session messages eagerly, but may
        #        use a tool to retrieve them on demand.
        # ------------------------------------------------------------
        self._updates: list[Message] = session.messages.copy()

        self._worker_queue: Queue = Queue()
        self._worker_task: Task | None = None

    def _start_worker(self):
        self._worker_task = create_task(self.worker())

    def get_state(self) -> dict[str, Any]:
        return {
            "updates": [asdict(update) for update in self._updates],
            "history": self.agent.get_state(),
        }

    def set_state(self, state: dict[str, Any]):
        self._updates = [Message(**update) for update in state["updates"]]
        self.agent.set_state(state["history"])

    async def update(self, message: Message):
        if self._worker_task is None:
            self._start_worker()
        await self._worker_queue.put(message)

    async def invoke(self, request: AgentRequest, secrets: dict[str, str] | None = None):
        if self._worker_task is None:
            self._start_worker()
        await self._worker_queue.put((request, secrets))

    async def run(self, request: AgentRequest, secrets: dict[str, str] | None = None) -> AgentResponse:
        response: AgentResponse | None = None

        # -------------------------------------
        #  TODO: trace query
        # -------------------------------------
        async with self.agent.mcp_servers(secrets=secrets):
            async for elem in self.agent.run(request=request, updates=self._updates):
                match elem:
                    case PermissionRequest():
                        # -------------------------------------
                        #  TODO: trace permission request
                        # -------------------------------------
                        await self.session.handle_permission_request(
                            request=elem, sender=self.agent.name, receiver=request.sender
                        )
                    case FeedbackRequest():
                        # -------------------------------------
                        #  TODO: trace feedback request
                        # -------------------------------------
                        await self.session.handle_feedback_request(
                            request=elem, sender=self.agent.name, receiver=request.sender
                        )
                    case AgentResponse():
                        # -------------------------------------
                        #  TODO: trace result
                        # -------------------------------------
                        response = replace(elem, request_id=request.id, message_id=request.message_id)

        assert response, "No response from agent run"
        return response

    async def worker(self):
        while True:
            item = await self._worker_queue.get()
            match item:
                case Message():
                    self._updates.append(item)
                case AgentRequest(query=query, sender=sender, id=request_id) as request, secrets:
                    self.session._run_context.set(
                        {"sender": sender, "secrets": secrets, "attachments": request.attachments}
                    )

                    try:
                        query = await self._expand_command(query, sender)
                        response = await self.run(replace(request, query=query), secrets)
                    except KeyError as e:
                        response = AgentResponse(
                            text=e.args[0],
                            request_id=request_id,
                        )
                        await self.session.handle_system_response(
                            response=response,
                            receiver=sender,
                        )
                    except Exception as e:
                        logger.exception(e)
                        response = AgentResponse(
                            text=f"Error executing agent '{self.agent.name}'.",
                            request_id=request_id,
                        )
                        await self.session.handle_system_response(
                            response=response,
                            receiver=sender,
                        )
                    else:
                        await self.session.handle_agent_response(
                            response=response, sender=self.agent.name, receiver=sender
                        )
                        self._updates = []

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
        if not re.match(r"^[a-zA-Z0-9_-]+$", command_name):
            return query

        # Try to load the command - let KeyError bubble up
        command_content = await self.session.command_store.load_command(command_name, sender)

        # Handle {ARGUMENTS} placeholder
        if "{ARGUMENTS}" in command_content:
            return command_content.replace("{ARGUMENTS}", arguments)
        elif arguments:
            # Append arguments after a newline if no placeholder
            return f"{command_content}\n{arguments}"
        else:
            return command_content


class Session:
    def __init__(self, id: str, manager: "SessionManager"):
        self.id = id
        self.manager = manager

        self.agent_registries: AgentRegistries = self.manager.agent_registries
        self.user_registry: UserRegistry = self.manager.user_registry
        self.permission_store: PermissionStore = self.manager.permission_store
        self.preference_store: DefaultPreferenceStore = self.manager.preference_store
        self.composio_config: ComposioConfig = self.manager.composio_config
        self.command_store: CommandStore = self.manager.command_store

        self._agents: dict[str, SessionAgent] = {}
        self._messages: list[Message] = []
        self._sync_task: Task | None = None

        self._gateway_queue: Queue = Queue()
        self._gateway_task: Task = create_task(self._gateway_worker())
        self._gateway: Gateway | None = None
        self._channel: str | None = None

        self._request_handler_queue: Queue = Queue()
        self._request_handler_task: Task = create_task(self._request_handler_worker())
        self._request_handler = self.manager.request_handler

        self._run_context = ContextVar[dict[str, Any]]("run_context")

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
    def channel(self) -> str | None:
        return self._channel

    @property
    def messages(self) -> list[Message]:
        return self._messages

    def set_gateway(self, gateway: Gateway):
        self._gateway = gateway

    def set_channel(self, channel: str):
        self._channel = channel

    def agent_names(self) -> set[str]:
        names = set(self._agents.keys())
        names |= self.agent_registries.get_registry(name=self.channel).get_registered_names()
        return names

    def _create_agent(self, name: str, tools: list | None = None) -> SessionAgent:
        registry = self.agent_registries.get_registry(name=self.channel)
        return SessionAgent(registry.create_agent(name, tools=tools), session=self)

    def _load_agent(self, agent_name: str):
        # tools: list[Callable] = [self.get_user_preferences]
        tools: list[Callable] = []
        if agent_name == "system":
            tools.append(self.run_agent)
        self._agents[agent_name] = self._create_agent(agent_name, tools=tools)

    async def _load_referenced_threads(self, text: str) -> list[Thread]:
        refs = self._extract_thread_references(text)
        return await self.manager.load_threads(refs)

    @staticmethod
    def _extract_thread_references(text: str) -> list[str]:
        return re.findall(r"thread:([a-zA-Z0-9.-]+)", text)

    @staticmethod
    def _extract_initial_mention(text: str):
        if not text:
            return None, text

        # Match '@name' at the beginning, with optional surrounding whitespace.
        match = re.match(r"^\s*@([/\w-]+)\s*([\s\S]*)", text)

        if match:
            # return mention and remaining text
            return match.group(1), match.group(2)

        return None, text

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str):
        if permission := await self.permission_store.get_permission(request.tool_name, receiver, self.id):
            request.respond(permission)
            return

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

    async def handle_gateway_message(
        self,
        text: str,
        sender: str,
        message_id: str | None = None,
        attachments: list[Attachment] | None = None,
    ):
        # first @mention, if any, in the message text is the receiver
        receiver, remaining_text = self._extract_initial_mention(text)

        # Load any threads referenced with `thread:...` in the message text.
        threads = await self._load_referenced_threads(text)

        # get stored preferences of message sender
        preferences = await self.get_user_preferences(sender)

        message = Message(
            text=remaining_text,
            sender=sender,
            receiver=receiver,
            threads=threads,
            attachments=attachments or [],
            id=message_id,
        )
        request = AgentRequest(
            query=message.text,
            sender=message.sender,
            receiver=message.receiver,
            threads=message.threads,
            attachments=message.attachments,
            preferences=preferences,
            message_id=message.id,
        )

        if receiver in self.agent_names():
            if receiver not in self._agents:
                self._load_agent(receiver)
            await self.update_agents(message, exclude=receiver)
            await self.invoke_agent(receiver, request)
        elif default := self.agent_registries.get_registry(name=self.channel).get_default_agent():
            if default not in self._agents:
                self._load_agent(default)
            await self.update_agents(message, exclude=default)
            await self.invoke_agent(default, request)

    async def update_agents(self, message: Message, exclude: str | None = None):
        # Add message to this session's message history. These are
        # the messages that users see on the platforms integrated
        # by gateways.
        self._messages.append(message)

        for agent_name, agent in self._agents.items():
            if agent_name != exclude:
                await agent.update(message)

    async def invoke_agent(self, agent_name: str, request: AgentRequest):
        activation = AgentActivation(
            agent_name=agent_name,
            message_id=request.message_id,
            request_id=request.id,
        )
        coro = self.gateway.handle_agent_activation(
            activation=activation,
            session_id=self.id,
        )
        await self._gateway_queue.put(coro)

        # get secrets of authenticated sender
        user_secrets = self.user_registry.get_secrets(request.sender) or {}
        mcp_vars = self.composio_config.mcp_config_vars()

        # invoke receiver agent with request
        await self._agents[agent_name].invoke(request, mcp_vars | user_secrets)

    # -------------------------------------
    #  Used as agent tool
    # -------------------------------------
    async def run_agent(self, agent_name: str, query: str) -> str:
        """Run an agent identified by agent_name with the given query and return its response."""

        try:
            agent = self._create_agent(agent_name, tools=[])
        except ValueError:
            return f'Agent "{agent_name}" not registered'

        run_context = self._run_context.get()

        request = AgentRequest(
            query=query,
            sender=run_context["sender"],
            receiver=agent_name,
            attachments=run_context["attachments"],
        )
        response = await agent.run(
            request=request,
            secrets=run_context["secrets"],
        )
        return response.text

    async def get_user_preferences(self, username: str) -> str | None:
        if preferences := await self.preference_store.get_preferences(username):
            return f"User preferences for {username}:\n{preferences}"
        return None

    def contains(self, id: str) -> bool:
        return any(message.id == id for message in self._messages)

    def root(self) -> Path:
        return self.manager.session_dir(self.id)

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
        try:
            state_dict = {
                "messages": [asdict(message) for message in self._messages],
                "agents": {name: adapter.get_state() for name, adapter in self._agents.items()},
            }
            await self.manager.save_session_state(self.id, state_dict)
        except Exception as e:
            logger.exception(e)

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
        agent_registries: AgentRegistries,
        user_registry: UserRegistry,
        permission_store: PermissionStore,
        preferences_store: DefaultPreferenceStore,
        request_handler: RequestHandler,
        composio_config: ComposioConfig,
        command_store: CommandStore,
        root_dir: Path = Path(".data", "sessions"),
    ):
        self.agent_registries = agent_registries
        self.user_registry = user_registry
        self.permission_store = permission_store
        self.preference_store = preferences_store
        self.request_handler = request_handler
        self.composio_config = composio_config
        self.command_store = command_store

        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, id: str) -> Session:
        return Session(id=id, manager=self)

    async def load_session(self, id: str) -> Session | None:
        if not await self.session_saved(id):
            return None
        session = self.create_session(id)
        await session.load()
        return session

    def session_dir(self, id: str) -> Path:
        return self.root_dir / id

    def session_path(self, id: str) -> Path:
        return self.session_dir(id) / "state.json"

    async def session_saved(self, id: str) -> bool:
        return await aiofiles.os.path.exists(str(self.session_path(id)))

    async def save_session_state(self, id: str, state: dict[str, Any]):
        session_path = self.session_path(id)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(session_path, "w") as f:
            await f.write(json.dumps(state, indent=2))

    async def load_session_state(self, id: str) -> dict[str, Any]:
        async with aiofiles.open(self.session_path(id), "r") as f:
            return json.loads(await f.read())

    async def load_thread(self, id: str) -> Thread:
        state = await self.load_session_state(id)
        messages = Thread.from_dicts(state["messages"])
        return Thread(session_id=id, messages=messages)

    async def load_threads(self, session_ids: list[str]) -> list[Thread]:
        threads = []
        for session_id in session_ids:
            if not await self.session_saved(session_id):
                continue
            threads.append(await self.load_thread(session_id))
        return threads
