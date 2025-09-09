import asyncio
import importlib
import inspect
import logging
import os
from abc import abstractmethod
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Coroutine, Generic, Sequence, Type, TypeVar

from pydantic_ai import Agent as AgentImpl
from pydantic_ai.builtin_tools import AbstractBuiltinTool
from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.messages import (
    BinaryContent,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import CombinedToolset, FunctionToolset, WrapperToolset
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
from hygroup.agent.default.utils import replace_variables
from hygroup.agent.utils import model_from_dict

D = TypeVar("D")

logger = logging.getLogger(__name__)


@dataclass
class MCPSettings:
    server_config: dict[str, Any]

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
    mcp_settings: list[MCPSettings] = field(default_factory=list)
    builtin_tools: list[Coroutine] = field(default_factory=list)
    tools: list[AbstractBuiltinTool] = field(default_factory=list)

    @staticmethod
    def serialize_builtin_tool(builtin_tool: AbstractBuiltinTool) -> dict[str, str]:
        result = asdict(builtin_tool)
        result["class"] = builtin_tool.__class__.__name__
        return result

    @staticmethod
    def deserialize_builtin_tool(tool_dict: dict[str, str]) -> AbstractBuiltinTool | None:
        return globals()[tool_dict.pop("class")](**tool_dict)

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

        # Serialize builtin tools
        serialized_builtin_tools = []
        for builtin_tool in self.builtin_tools:
            serialized = self.serialize_builtin_tool(builtin_tool)
            if serialized is not None:
                serialized_builtin_tools.append(serialized)
        data["builtin_tools"] = serialized_builtin_tools

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

        # Deserialize builtin tools
        builtin_tools = []
        for builtin_tool_dict in data.get("builtin_tools", []):
            builtin_tool = AgentSettings.deserialize_builtin_tool(builtin_tool_dict)
            if builtin_tool is not None:
                builtin_tools.append(builtin_tool)
        data["builtin_tools"] = builtin_tools

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
            builtin_tools=settings.builtin_tools,
            output_type=output_type,
        )

        self._history = []  # type: ignore
        self._mcp_servers: list[MCPServer] = []
        self._fn_toolset: FunctionToolset = FunctionToolset(tools=settings.tools)

        if settings.human_feedback:
            self.tool(self.ask_user)

    def get_state(self) -> Any:
        return to_jsonable_python(self._history, bytes_mode="base64")

    def set_state(self, state: Any):
        self._history = ModelMessagesTypeAdapter.validate_python(state)

    def ask_user(self, question: str) -> str:
        """A tool to ask a user for clarifications or further input if needed.

        Args:
            question: The question to ask the user.
        """
        return ""  # answer is created by tool interceptor

    def tool(self, coro):
        self._fn_toolset.add_function(coro)
        return coro

    @asynccontextmanager
    async def mcp_servers(self, secrets: dict[str, str] | None = None):
        with self._configure_mcp_servers(dict(os.environ) | (secrets or {})):
            async with self.agent:
                yield

    @contextmanager
    def _configure_mcp_servers(self, variables: dict[str, str]):
        for settings in self.settings.mcp_settings:
            result = replace_variables(settings.server_config, variables)
            settings = MCPSettings(result.replaced)
            if result.missing_variables:
                logger.warning(
                    f"Variables {result.missing_variables} missing for "
                    f"configuring MCP server {settings.server_config}. "
                    f"Agent '{self.name}' will not use this MCP server."
                )
            else:
                self._mcp_servers.append(settings.server())
        try:
            yield
        finally:
            self._mcp_servers.clear()

    async def run(
        self,
        request: AgentRequest,
        updates: Sequence[Message] = (),
    ) -> AsyncIterator[AgentResponse | PermissionRequest | FeedbackRequest]:
        queue = asyncio.Queue()  # type: ignore

        agent_tools = CombinedToolset(toolsets=[self._fn_toolset, *self._mcp_servers])
        agent_tools = ToolInterceptor(wrapped=agent_tools, queue=queue)

        task = asyncio.create_task(self._run(request, updates, agent_tools))

        while True:
            if task.done() and task.exception():
                break
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

        await task

    async def _run(
        self,
        request: AgentRequest,
        updates: Sequence[Message],
        tool_interceptor: "ToolInterceptor",
    ):
        system_prompt_part: SystemPromptPart | None = None

        if request.preferences:
            message_history = self._history + self._preferences_conversation(
                request.preferences,
                sender=request.sender,
            )
            if len(self._history) == 0:
                system_prompt_part = SystemPromptPart(content=self.settings.instructions)
                message_history[0].parts.insert(0, system_prompt_part)
        else:
            message_history = self._history

        user_prompt = []

        if request.attachments:
            for attachment in request.attachments:
                user_prompt.append(f'Attachment name="{attachment.name}": ')
                user_prompt.append(
                    BinaryContent(
                        data=await attachment.bytes(),
                        media_type=attachment.media_type,
                    )
                )

        user_prompt.append(self.input_formatter(request, updates))

        result: AgentRunResult = await self.agent.run(
            user_prompt=user_prompt,
            toolsets=[tool_interceptor],
            message_history=message_history,
        )
        response = AgentResponse(text=self._text(result.output))
        await tool_interceptor.queue.put(response)

        new_messages = result.new_messages()
        if system_prompt_part is not None:
            new_messages[0].parts.insert(0, system_prompt_part)
        self._history.extend(new_messages)

    @staticmethod
    def _preferences_conversation(preferences: str, sender: str) -> list[ModelRequest | ModelResponse]:
        input_part = UserPromptPart(
            content=f"Call get_user_preferences({sender})",
        )
        tool_call_part = ToolCallPart(
            tool_name="get_user_preferences",
            args={"username": sender},
        )
        tool_return_part = ToolReturnPart(
            tool_name="get_user_preferences",
            content=preferences,
            tool_call_id=tool_call_part.tool_call_id,
        )

        return [
            ModelRequest(parts=[input_part]),
            ModelResponse(parts=[tool_call_part]),
            ModelRequest(parts=[tool_return_part]),
        ]

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


@dataclass
class ToolInterceptor(WrapperToolset):
    queue: asyncio.Queue

    async def call_tool(self, name: str, tool_args: dict[str, Any], ctx, tool) -> Any:
        if name == "ask_user":
            feedback_request = FeedbackRequest(
                question=tool_args.get("question", ""),
                ftr=asyncio.Future(),
            )
            await self.queue.put(feedback_request)
            return await feedback_request.response()
        else:
            permission_request = PermissionRequest(
                tool_name=name,
                tool_args=(),
                tool_kwargs=tool_args,
                ftr=asyncio.Future(),
            )
            await self.queue.put(permission_request)
            if await permission_request.response():
                return await self.wrapped.call_tool(name, tool_args, ctx, tool)
            else:
                return f"Permission denied calling tool '{name}'"
