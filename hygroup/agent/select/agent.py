from dataclasses import dataclass, field

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelSettings
from pydantic_ai.models.google import GoogleModelSettings
from pydantic_core import to_jsonable_python

from hygroup.agent.base import AgentRegistry, Message
from hygroup.agent.select.prompt import SYSTEM_PROMPT, format_message
from hygroup.agent.utils import model_from_dict


class AgentSelection(BaseModel):
    agent_name: str | None = None
    query: str | None = None


@dataclass
class AgentSelectorSettings:
    instructions: str = SYSTEM_PROMPT
    model: str | dict = "gemini-2.5-flash"
    model_settings: ModelSettings = field(
        default_factory=lambda: GoogleModelSettings(
            max_tokens=1024,
            google_thinking_config={
                "thinking_budget": 512,
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
            system_prompt=self.settings.instructions,
            output_type=AgentSelection,
        )
        self._agent.tool_plain(registry.get_registered_agents)
        self._history = []  # type: ignore

    async def run(self, message: Message) -> AgentSelection:
        prompt = format_message(message)
        result = await self._agent.run(
            user_prompt=prompt,
            message_history=self._history,
        )
        self._history.extend(result.new_messages())
        return result.output

    async def add(self, message: Message):
        init = len(self._history) == 0
        parts = []

        if init:
            parts.append(SystemPromptPart(content=self.settings.instructions))

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

    def get_state(self):
        """Get the serialized state of the selector agent."""
        return to_jsonable_python(self._history)

    def set_state(self, state):
        """Set the state of the selector agent from serialized data."""
        self._history = ModelMessagesTypeAdapter.validate_python(state)
