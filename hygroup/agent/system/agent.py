from pathlib import Path

from pydantic import BaseModel

from hygroup.agent.default.agent import AgentBase, AgentRequest, AgentSettings
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
        self.registered_agents = registered_agents

    def _prep(self, request: AgentRequest, user_prompt: list):
        if self.registered_agents and not self._history:
            user_prompt.append(self.registered_agents)

    def _text(self, data: SystemAgentOutput) -> str:
        if data.response is None:
            return ""
        else:
            return data.response.strip()
