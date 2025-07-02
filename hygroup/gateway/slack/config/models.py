from dataclasses import dataclass, field
from typing import Any, Dict


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
    model: Dict[str, Any] | str
    instructions: str
    mcp_settings: list[dict[str, Any]] = field(default_factory=list)
    handoff: bool = False
    emoji: str | None = None

    @classmethod
    def from_agent_config(cls, agent_config: dict[str, Any]) -> "AgentViewModel":
        return cls(
            name=agent_config["name"],
            description=agent_config["description"],
            model=agent_config["settings"]["model"],
            instructions=agent_config["settings"]["instructions"],
            mcp_settings=agent_config["settings"]["mcp_settings"],
            handoff=agent_config["handoff"],
            emoji=agent_config.get("emoji"),
        )
