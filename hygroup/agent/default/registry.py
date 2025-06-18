from pathlib import Path
from typing import Any

from tinydb import Query, TinyDB

from hygroup.agent.base import AgentRegistry
from hygroup.agent.default.agent import AgentBase, AgentSettings, DefaultAgent, HandoffAgent
from hygroup.utils import arun


class DefaultAgentRegistry(AgentRegistry):
    """TinyDB-based agent registry for persistent agent config storage."""

    def __init__(self, registry_path: Path | str = Path(".data", "agents", "registry.json")):
        """Initialize the registry with TinyDB storage.

        Args:
            registry_path: Path to the registry file
        """
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(self.registry_path), indent=2)

    async def create_agent(self, name: str) -> AgentBase:
        """Create an agent from config registered under `name`."""
        doc = await self.get_config(name)

        if doc is None:
            raise ValueError(f"No agent registered with name '{name}'")

        settings = AgentSettings.from_dict(doc["settings"])

        if doc["handoff"]:
            return HandoffAgent(name=name, settings=settings)
        else:
            return DefaultAgent(name=name, settings=settings)

    async def registered_names(self) -> set[str]:
        descriptions = await self.get_descriptions()
        return set(descriptions.keys())

    async def get_config(self, name: str) -> dict[str, Any]:
        """Return the configuration for an agent."""
        Agent = Query()
        return await arun(self.db.get, Agent.name == name)

    async def add_config(
        self,
        name: str,
        description: str,
        settings: AgentSettings,
        handoff: bool = False,
    ):
        """Add settings for an agent."""
        Agent = Query()

        # Check if name already exists
        existing = await arun(self.db.get, Agent.name == name)
        if existing is not None:
            raise ValueError(f"Agent with name '{name}' already exists")

        # Convert AgentSettings to dict for storage
        settings_dict = settings.to_dict()

        # Create document
        doc = {"name": name, "description": description, "handoff": handoff, "settings": settings_dict}

        # Insert document
        await arun(self.db.insert, doc)

    async def remove_config(self, name: str):
        """Remove settings for an agent."""
        Agent = Query()
        removed_ids = await arun(self.db.remove, Agent.name == name)

        if not removed_ids:
            raise ValueError(f"No agent registered with name '{name}'")

    async def remove_configs(self):
        await arun(self.db.drop_tables)

    async def get_descriptions(self) -> dict[str, str]:
        """Return a dictionary of agent names and their descriptions."""
        docs = await arun(self.db.all)
        return {doc["name"]: doc["description"] for doc in docs}

    async def get_registered_agents(self) -> str:
        """Get a list of registered agents in the format:

        - [agent name 1]: [agent description 1]
        - [agent name 2]: [agent description 2]
        - ...

        Returns:
            A string with the list of registered agents.
        """

        configs = await self.get_descriptions()
        return "\n".join([f"- {name}: {description}" for name, description in configs.items()])
