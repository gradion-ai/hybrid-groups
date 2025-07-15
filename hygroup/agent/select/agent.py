from asyncio import Future
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelSettings
from pydantic_ai.models.google import GoogleModelSettings
from pydantic_core import to_jsonable_python

from hygroup.agent.base import AgentRegistry, Message
from hygroup.agent.default.prompt import format_message
from hygroup.agent.select.prompt import INSTRUCTIONS
from hygroup.agent.utils import model_from_dict


class AgentSelection(BaseModel):
    agent_name: str | None = None
    query: str | None = None


@dataclass
class AgentSelectionResult:
    selection: AgentSelection
    thoughts: list[str] = field(default_factory=list)


@dataclass
class AgentSelectionConfirmationResponse:
    confirmed: bool
    comment: str | None = None


@dataclass
class AgentSelectionConfirmationRequest:
    selection_result: AgentSelectionResult
    ftr: Future

    async def response(self) -> AgentSelectionConfirmationResponse:
        return await self.ftr

    def respond(self, confirmed: bool, comment: str | None = None):
        self.ftr.set_result(AgentSelectionConfirmationResponse(confirmed=confirmed, comment=comment))


@dataclass
class AgentSelectorSettings:
    instructions: str = INSTRUCTIONS
    """
    Instructions to the selector agent.
    """

    instructions_file: Path | str | None = None
    """
    If exists, the instructions will be read from the file.
    """

    model: str | dict = "gemini-2.5-flash"
    model_settings: ModelSettings = field(
        default_factory=lambda: GoogleModelSettings(
            google_thinking_config={
                "include_thoughts": True,
            },
        )
    )


class AgentSelector:
    def __init__(
        self,
        registry: AgentRegistry,
        settings: AgentSelectorSettings | None = None,
    ):
        self.registry = registry
        self.settings = settings or AgentSelectorSettings()

        if isinstance(self.settings.model, dict):
            model = model_from_dict(self.settings.model)
        else:
            model = self.settings.model

        self._agent = Agent(
            model=model,
            model_settings=self.settings.model_settings,
            instructions=self.instructions,
            output_type=AgentSelection,
        )
        self._agent.tool_plain(registry.get_registered_agents)
        self._history = []  # type: ignore

    def get_state(self):
        """Get the serialized state of the selector agent."""
        return to_jsonable_python(self._history)

    def set_state(self, state):
        """Set the state of the selector agent from serialized data."""
        self._history = ModelMessagesTypeAdapter.validate_python(state)

    async def instructions(self) -> str:
        if self.settings.instructions_file and Path(self.settings.instructions_file).exists():
            async with aiofiles.open(self.settings.instructions_file, "r") as f:
                return await f.read()
        else:
            return self.settings.instructions

    async def run(self, message: Message) -> AgentSelectionResult:
        prompt = format_message(message)
        result = await self._agent.run(
            user_prompt=prompt,
            message_history=self._history,
        )
        thoughts = []
        for msg in result.new_messages():
            self._history.append(msg)
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ThinkingPart) and part.has_content():
                        thoughts.append(part.content)

        return AgentSelectionResult(selection=result.output, thoughts=thoughts)

    async def add(self, message: Message):
        init = len(self._history) == 0
        parts = []

        parts.append(UserPromptPart(content=format_message(message)))
        self._history.append(ModelRequest(parts=parts))

        if init:
            info = await self.registry.get_registered_agents()
            self._add_agents_info(info=info)

        self._add_empty_result()

    def _add_empty_result(self):
        tool_req = ToolCallPart(
            tool_name="final_result",
            args={"agent_name": None, "query": None, "reasoning": None},
        )
        tool_ret = ToolReturnPart(
            tool_name="final_result",
            tool_call_id=tool_req.tool_call_id,
            content="Final result processed",
        )
        self._history.extend(
            [
                ModelResponse(parts=[tool_req]),
                ModelRequest(parts=[tool_ret]),
            ]
        )

    def _add_agents_info(self, info: str):
        tool_req = ToolCallPart(
            tool_name="get_registered_agents",
            args={},
        )
        tool_ret = ToolReturnPart(
            tool_name="get_registered_agents",
            tool_call_id=tool_req.tool_call_id,
            content=info,
        )
        self._history.extend(
            [
                ModelResponse(parts=[tool_req]),
                ModelRequest(parts=[tool_ret]),
            ]
        )
