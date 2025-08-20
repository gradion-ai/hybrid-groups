import asyncio
import importlib
import inspect
import logging
import os
from abc import abstractmethod
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Generic, Iterator, Sequence, Type, TypeVar

from pydantic_ai import Agent as AgentImpl
from pydantic_ai import CallToolsNode, ModelRequestNode
from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
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
from hygroup.agent.default.utils import replace_variables
from hygroup.agent.prompt import InputFormatter, format_input
from hygroup.agent.utils import model_from_dict

D = TypeVar("D")

logger = logging.getLogger(__name__)


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

    def session_mcp_settings(self) -> list[MCPSettings]:
        return [s for s in self.mcp_settings if s.session_scope]

    def request_mcp_settings(self) -> list[MCPSettings]:
        return [s for s in self.mcp_settings if not s.session_scope]

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

        self.agent: AgentImpl[None, D] = AgentImpl(
            model=model,
            system_prompt=settings.instructions,
            model_settings=settings.model_settings,
            output_type=output_type,
        )

        self._history = []  # type: ignore
        self._session_mcp_servers: list[MCPServer] = []
        self._request_mcp_servers: list[MCPServer] = []

        for tool in settings.tools:
            self.tool(tool)

        if settings.human_feedback:
            self.tool(self.ask_user)

    def get_state(self) -> Any:
        return to_jsonable_python(self._history)

    def set_state(self, state: Any):
        self._history = ModelMessagesTypeAdapter.validate_python(state)

    def ask_user(self, question: str) -> str:
        """A tool to ask a user for clarifications or further input if needed.

        Args:
            question: The question to ask the user.
        """
        return ""  # answer is overridden in self.run()

    def tool(self, coro):
        self.agent.tool_plain(coro)
        return coro

    @asynccontextmanager
    async def session_scope(self):
        with self._configure_mcp_servers(self.settings.session_mcp_settings(), dict(os.environ)) as servers:
            async with self._run_mcp_servers(servers):
                self._session_mcp_servers = servers
                yield
                self._session_mcp_servers.clear()

    @asynccontextmanager
    async def request_scope(self, secrets: dict[str, str] | None = None):
        with self._configure_mcp_servers(
            self.settings.request_mcp_settings(), dict(os.environ) | (secrets or {})
        ) as servers:
            async with self._run_mcp_servers(servers):
                self._request_mcp_servers = servers
                yield
                self._request_mcp_servers.clear()

    async def run(
        self,
        request: AgentRequest,
        updates: Sequence[Message] = (),
    ) -> AsyncIterator[AgentResponse | PermissionRequest | FeedbackRequest]:
        stopped = False

        agent_input = self.input_formatter(request, updates)
        mcp_servers = self._session_mcp_servers + self._request_mcp_servers

        async with self.agent.iter(agent_input, toolsets=mcp_servers, message_history=self._history) as agent_run:
            feedback_requests: dict[str, FeedbackRequest] = {}
            feedback_request: FeedbackRequest
            permission_request: PermissionRequest

            async for node in agent_run:
                if stopped:
                    break
                match node:
                    case ModelRequestNode(request=ModelRequest(parts=parts)):
                        for part in parts:
                            match part:
                                case ToolReturnPart(tool_name="ask_user", tool_call_id=tool_call_id):
                                    feedback_request = feedback_requests.pop(tool_call_id)
                                    part.content = await feedback_request.response()
                    case CallToolsNode(model_response=ModelResponse(parts=parts)):
                        for part in parts:
                            match part:
                                case ToolCallPart(tool_name="ask_user", tool_call_id=tool_call_id):
                                    feedback_request = FeedbackRequest(
                                        question=part.args_as_dict().get("question"),
                                        ftr=asyncio.Future(),
                                    )
                                    yield feedback_request
                                    feedback_requests[tool_call_id] = feedback_request
                                case ToolCallPart(tool_name=tool_name):
                                    permission_request = PermissionRequest(
                                        tool_name=tool_name,
                                        tool_args=(),
                                        tool_kwargs=part.args_as_dict(),
                                        ftr=asyncio.Future(),
                                    )
                                    yield permission_request
                                    if not await permission_request.response():
                                        yield AgentResponse(text=f"Permission denied calling {tool_name}", final=True)
                                        stopped = True
                                        break

            if not stopped:
                yield AgentResponse(text=self._text(agent_run.result.output), final=True)
                self._history.extend(agent_run.result.new_messages())

    @contextmanager
    def _configure_mcp_servers(
        self, mcp_settings: list[MCPSettings], variables: dict[str, str]
    ) -> Iterator[list[MCPServer]]:
        mcp_servers: list[MCPServer] = []
        for settings in mcp_settings:
            result = replace_variables(settings.server_config, variables)
            settings = MCPSettings(result.replaced, settings.session_scope)
            if result.missing_variables:
                logger.warning(
                    f"Variables {result.missing_variables} missing for "
                    f"configuring MCP server {settings.server_config}. "
                    f"Agent '{self.name}' will not use this MCP server."
                )
            else:
                mcp_servers.append(settings.server())
        yield mcp_servers

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

    @abstractmethod
    def _text(self, data: D) -> str: ...


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
