from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    field: str
    message: str


@dataclass
class AgentListViewModel:
    name: str
    description: str
    emoji: str | None = None

    @classmethod
    def from_agent_config(cls, agent_config: dict[str, Any]) -> "AgentListViewModel":
        return cls(
            name=agent_config["name"],
            description=agent_config["description"],
            emoji=agent_config.get("emoji"),
        )


@dataclass
class AgentViewModel:
    name: str
    description: str
    model: dict[str, Any] | str
    instructions: str
    mcp_settings: list[dict[str, Any]] = field(default_factory=list)
    model_settings: dict[str, Any] | None = None
    tools: list[dict[str, str]] = field(default_factory=list)
    handoff: bool = False
    emoji: str | None = None

    @classmethod
    def from_agent_config(cls, agent_config: dict[str, Any]) -> "AgentViewModel":
        return cls(
            name=agent_config["name"],
            description=agent_config["description"],
            model=agent_config["settings"]["model"],
            instructions=agent_config["settings"]["instructions"],
            mcp_settings=agent_config["settings"].get("mcp_settings", []),
            model_settings=agent_config["settings"].get("model_settings"),
            tools=agent_config["settings"].get("tools", []),
            handoff=agent_config["handoff"],
            emoji=agent_config.get("emoji"),
        )
