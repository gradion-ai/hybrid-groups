from pathlib import Path

from pydantic import BaseModel
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from hygroup.agent.default.agent import AgentBase, AgentSettings
from hygroup.agent.default.prompt import InputFormatter, format_input


def system_agent_instructions() -> str:
    prompt_path = Path(__file__).parent / "prompt.md"
    return prompt_path.read_text()


class SystemAgentOutput(BaseModel):
    response: str | None = None


class SystemAgent(AgentBase[SystemAgentOutput]):
    def __init__(
        self,
        settings: AgentSettings,
        input_formatter: InputFormatter = format_input,
        registered_agents: str | None = None,
    ):
        super().__init__(
            name="system",
            settings=settings,
            input_formatter=input_formatter,
            output_type=SystemAgentOutput,
        )
        if registered_agents is not None:
            self._history = self._registered_agents_conversation(registered_agents)

    def _registered_agents_conversation(self, registered_agents: str):
        tool_call_part = ToolCallPart(
            tool_name="get_registered_agents",
        )
        tool_return_part = ToolReturnPart(
            tool_name="get_registered_agents",
            content=registered_agents,
            tool_call_id=tool_call_part.tool_call_id,
        )

        return [
            ModelRequest(
                parts=[
                    SystemPromptPart(content=self.settings.instructions),
                    UserPromptPart(content="Call get_registered_agents()"),
                ],
            ),
            ModelResponse(parts=[tool_call_part]),
            ModelRequest(parts=[tool_return_part]),
        ]

    def _text(self, data: SystemAgentOutput) -> str:
        if data.response is None:
            return ""
        else:
            return data.response.strip()
