import asyncio
import importlib
import inspect
import os
from abc import abstractmethod
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Generic, Iterator, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel, Field
from pydantic_ai import Agent as AgentImpl
from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.settings import ModelSettings
from pydantic_core import to_jsonable_python

from hygroup.agent.base import (
    Agent,
    AgentRequest,
    AgentResponse,
    FeedbackRequest,
    Message,
    PermissionRequest,
)
from hygroup.agent.default.prompt import InputFormatter, format_input
from hygroup.agent.default.utils import resolve_config_variables
from hygroup.agent.utils import model_from_dict

D = TypeVar("D")


@dataclass
class MCPSettings:
    server_config: dict[str, Any]
    session_scope: bool = True

    def server(self) -> MCPServer:
        if "command" in self.server_config:
            return MCPServerStdio(**self.server_config)
        else:
            return MCPServerStreamableHTTP(**self.server_config)


@dataclass
class AgentSettings:
    model: str | dict
    instructions: str
    human_feedback: bool = False
    model_settings: ModelSettings | None = None
    mcp_settings: Sequence[MCPSettings] = field(default_factory=list)
    tools: Sequence[Callable] = field(default_factory=list)

    @staticmethod
    def serialize_tool(tool: Callable) -> dict[str, str] | None:
        """Serialize a callable tool to its module and function name.

        Returns None for lambdas, built-ins, or other non-regular functions.
        """
        try:
            tool_name = tool.__name__
            module_name = tool.__module__
            if module_name == "__main__":
                module = inspect.getmodule(tool)
                if module_file := getattr(module, "__file__", None):
                    filepath = Path(module_file).resolve()
                    root = Path.cwd()
                    if filepath.is_relative_to(root):
                        relpath = filepath.relative_to(root)
                        if relpath.suffix == ".py":
                            module_name = ".".join(relpath.with_suffix("").parts)

            return {"module": module_name, "function": tool_name}
        except AttributeError:
            return None

    @staticmethod
    def deserialize_tool(tool_dict: dict[str, str]) -> Callable | None:
        """Deserialize a tool from its module and function name.

        Returns None if the tool cannot be imported, printing an error message.
        """
        try:
            module = importlib.import_module(tool_dict["module"])
            return getattr(module, tool_dict["function"])
        except (ImportError, AttributeError) as e:
            print(f"Error importing tool {tool_dict['module']}.{tool_dict['function']}: {e}")
            return None

    def to_dict(self) -> dict[str, Any]:
        """Convert AgentSettings to dict, serializing tools."""
        data = asdict(self)
        # Serialize tools
        serialized_tools = []
        for tool in self.tools:
            serialized = self.serialize_tool(tool)
            if serialized is not None:
                serialized_tools.append(serialized)
        data["tools"] = serialized_tools
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AgentSettings":
        data = data.copy()
        data["mcp_settings"] = [MCPSettings(**s) for s in data.get("mcp_settings", [])]
        # Deserialize tools
        tools = []
        for tool_dict in data.get("tools", []):
            tool = AgentSettings.deserialize_tool(tool_dict)
            if tool is not None:
                tools.append(tool)
        data["tools"] = tools
        return AgentSettings(**data)


class AgentBase(Generic[D], Agent):
    def __init__(
        self,
        name: str,
        settings: AgentSettings,
        input_formatter: InputFormatter,
        output_type: Type[D],
    ):
        super().__init__(name)
        self.settings = settings
        self.input_formatter = input_formatter

        if isinstance(settings.model, dict):
            model = model_from_dict(settings.model)
        else:
            model = settings.model

        # delegate agent
        self.agent: AgentImpl[None, D] = AgentImpl(
            model=model,
            system_prompt=settings.instructions,
            model_settings=settings.model_settings,
            output_type=output_type,
        )

        self._history = []  # type: ignore
        self._ctx_queue = ContextVar[asyncio.Queue]("queue")
        self._ctx_secrets = ContextVar[bool]("secrets")

        # references servers with patched call_tool methods
        self._session_mcp_servers: list[MCPServer] = []
        self._request_mcp_servers: list[MCPServer] = []
        self.agent._mcp_servers = []

        for mcp_settings in settings.mcp_settings:
            # register server with and patch call_tool method
            self.server(requires_permission=True)(mcp_settings)

        for tool in settings.tools:
            self.tool(requires_permission=True)(tool)

        if settings.human_feedback:
            # no permission required for asking for user feedback
            self.tool(requires_permission=False)(self.ask_user)

    def get_state(self) -> Any:
        return to_jsonable_python(self._history)

    def set_state(self, state: Any):
        self._history = ModelMessagesTypeAdapter.validate_python(state)

    @asynccontextmanager
    async def session_scope(self):
        with self._configure_mcp_servers(self._session_mcp_servers, dict(os.environ)) as servers:
            async with self._run_mcp_servers(servers):
                yield

    @asynccontextmanager
    async def request_scope(self, secrets: dict[str, str] | None = None):
        self._ctx_secrets.set(secrets is not None)
        with self._configure_mcp_servers(self._request_mcp_servers, dict(os.environ) | (secrets or {})) as servers:
            async with self._run_mcp_servers(servers):
                yield

    async def run(
        self,
        request: AgentRequest,
        updates: Sequence[Message] = (),
        stream: bool = False,
    ) -> AsyncIterator[AgentResponse | PermissionRequest | FeedbackRequest]:
        queue = asyncio.Queue()  # type: ignore
        self._ctx_queue.set(queue)

        task = asyncio.create_task(self._run(request=request, updates=updates, stream=stream))

        while True:
            if task.done() and task.exception():
                raise task.exception()  # type: ignore
            try:
                obj = queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.1)
                continue
            else:
                yield obj
                match obj:
                    case AgentResponse(final=True):
                        break

    async def _run(self, request: AgentRequest, updates: Sequence[Message], stream: bool):
        queue = self._ctx_queue.get()
        agent_input = self.input_formatter(request, self.name, updates)

        if stream:
            async with self.agent.run_stream(agent_input, message_history=self._history) as result:
                stream_pos = 0
                async for structured_message, is_last in result.stream_structured():
                    data = await result.validate_structured_output(structured_message, allow_partial=not is_last)
                    if not is_last:
                        text = self._text(data)
                        response = AgentResponse(text=text[stream_pos:], final=False, handoffs={})
                        stream_pos = len(text)
                        if response.text:
                            await queue.put(response)
        else:
            result = await self.agent.run(agent_input, message_history=self._history)
            data = result.output

        await queue.put(AgentResponse(text=self._text(data), final=True, handoffs=self._handoffs(data)))
        self._history.extend(result.new_messages())

    @staticmethod
    @asynccontextmanager
    async def _run_mcp_servers(mcp_servers: list[MCPServer]):
        exit_stack = AsyncExitStack()
        try:
            for mcp_server in mcp_servers:
                await exit_stack.enter_async_context(mcp_server)
            yield
        finally:
            await exit_stack.aclose()

    @staticmethod
    @contextmanager
    def _configure_mcp_servers(
        mcp_servers: list[MCPServer], config_values: dict[str, str]
    ) -> Iterator[list[MCPServer]]:
        backups = []

        try:
            for server in mcp_servers:
                match server:
                    case MCPServerStdio() if server.env is not None:
                        new_env, updated = resolve_config_variables(server.env, config_values)
                        if updated:
                            backups.append((server, "env", dict(server.env)))
                            server.env = new_env
                    case MCPServerStreamableHTTP() if server.headers is not None:
                        new_headers, updated = resolve_config_variables(server.headers, config_values)
                        if updated:
                            backups.append((server, "headers", dict(server.headers)))
                            server.headers = new_headers
                    case _:
                        pass

            yield mcp_servers

        finally:
            for server, field_name, original_value in reversed(backups):
                setattr(server, field_name, original_value)

    @abstractmethod
    def _text(self, data: D) -> str: ...

    def _handoffs(self, data: D) -> dict[str, str]:
        return {}

    async def ask_user(self, question: str) -> str:
        """Ask the user for clarifications or further input if you cannot complete the task."""
        queue = self._ctx_queue.get()
        request = FeedbackRequest(question=question, ftr=asyncio.Future())
        await queue.put(request)
        return await request.response()

    def tool(self, requires_permission: bool = True):
        """Register a tool with the agent."""

        def decorator(coro):
            @wraps(coro)
            async def request_permission(*args, **kwargs):
                request = PermissionRequest(coro.__name__, args, kwargs, ftr=asyncio.Future())
                return await self._request_permission(coro, args, kwargs, request)

            if requires_permission:
                # register wrapped func as agent tool
                return self.agent.tool_plain(request_permission)
            else:
                # register func as agent tool
                return self.agent.tool_plain(coro)

        return decorator

    def server(self, requires_permission: bool = True):
        """Register an MCP server with the agent."""

        def decorator(settings: MCPSettings):
            server = settings.server()

            # keep a reference to the non-patched call_tool method
            call_tool = server.call_tool

            @wraps(call_tool)
            async def request_permission(tool_name: str, arguments: dict[str, Any]):
                as_user = self._ctx_secrets.get(False) and not settings.session_scope
                request = PermissionRequest(tool_name, (), arguments, asyncio.Future(), as_user)
                return await self._request_permission(call_tool, (tool_name, arguments), {}, request)

            if requires_permission:
                # patch call_tool method to request permission
                server.call_tool = request_permission

            # register server with delegeate agent
            self.agent._mcp_servers.append(server)

            # register server with agent wrapper
            if settings.session_scope:
                self._session_mcp_servers.append(server)
            else:
                self._request_mcp_servers.append(server)

        return decorator

    async def _request_permission(self, coro, args, kwargs, request: PermissionRequest):
        queue = self._ctx_queue.get()
        await queue.put(request)

        if await request.response():
            return await coro(*args, **kwargs)
        else:
            return f"Permission denied calling {request.call}"


class Handoff(BaseModel):
    """Response to the user with optional handoff to an agent."""

    response: str = Field(description="Response text to the user. Can be a partial response.")

    handoff_agent: Optional[str] = Field(description="Name of the agent to handoff to.", default=None)
    handoff_query: Optional[str] = Field(description="Query to handoff to the agent.", default=None)

    def handoffs(self) -> dict[str, str]:
        return {self.handoff_agent: self.handoff_query} if self.handoff_agent and self.handoff_query else {}


class HandoffAgent(AgentBase[Handoff]):
    def __init__(
        self,
        name: str,
        settings: AgentSettings,
        input_formatter: InputFormatter = format_input,
    ):
        super().__init__(
            name=name,
            settings=settings,
            input_formatter=input_formatter,
            output_type=Handoff,
        )

    def _text(self, data: Handoff) -> str:
        return data.response

    def _handoffs(self, data: Handoff) -> dict[str, str]:
        return data.handoffs()


class DefaultAgent(AgentBase[str]):
    def __init__(
        self,
        name: str,
        settings: AgentSettings,
        input_formatter: InputFormatter = format_input,
    ):
        super().__init__(
            output_type=str,
            name=name,
            settings=settings,
            input_formatter=input_formatter,
        )

    def _text(self, data: str) -> str:
        return data


AgentFactory = Callable[[], AgentBase]
