from pathlib import Path

from pydantic import BaseModel
from pydantic_ai.models.google import GoogleModelSettings

from hygroup.agent.default.agent import AgentBase, AgentSettings
from hygroup.agent.default.prompt import InputFormatter
from hygroup.agent.system.prompt import format_input


def system_agent_instructions() -> str:
    prompt_path = Path(__file__).parent / "prompt.md"
    return prompt_path.read_text()


system_agent_settings = AgentSettings(
    instructions=system_agent_instructions(),
    model="gemini-2.5-flash",
    model_settings=GoogleModelSettings(
        google_thinking_config={
            "include_thoughts": True,
        }
    ),
)


class SystemAgentOutput(BaseModel):
    response: str | None = None


class SystemAgent(AgentBase[SystemAgentOutput]):
    def __init__(
        self,
        settings: AgentSettings = system_agent_settings,
        input_formatter: InputFormatter = format_input,
    ):
        super().__init__(
            name="system",
            settings=settings,
            input_formatter=input_formatter,
            output_type=SystemAgentOutput,
        )

    def _text(self, data: SystemAgentOutput) -> str:
        if data.response is None:
            return ""
        else:
            return data.response.strip()
