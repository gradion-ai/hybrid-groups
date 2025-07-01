from pathlib import Path
from typing import Any

from tinydb import Query, TinyDB

from hygroup.agent.base import AgentRegistry
from hygroup.agent.default.agent import AgentBase, AgentFactory, AgentSettings, DefaultAgent, HandoffAgent
from hygroup.utils import arun


class DefaultAgentRegistry(AgentRegistry):
    """TinyDB-based agent registry for persistent agent config storage."""

    def __init__(self, registry_path: Path | str = Path(".data", "agents", "registry.json")):
        """Initialize the registry with TinyDB storage.

        Args:
            registry_path: Path to the registry file
        """
        self.factories: dict[str, dict[str, Any]] = {}
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(self.registry_path), indent=2)

    def add_factory(self, name: str, description: str, factory: AgentFactory):
        self.factories[name] = {"name": name, "description": description, "factory": factory}

    async def create_agent(self, name: str) -> AgentBase:
        """Create an agent from config or factory registered under `name`."""
        if doc := self.factories.get(name):
            return doc["factory"]()

        doc = await self.get_config(name)

        if doc is None:
            raise ValueError(f"No agent registered with name '{name}'")

        settings = AgentSettings.from_dict(doc["settings"])

        if doc["handoff"]:
            return HandoffAgent(name=name, settings=settings)
        else:
            return DefaultAgent(name=name, settings=settings)

    async def get_registered_names(self) -> set[str]:
        descriptions = await self.get_descriptions()
        return set(descriptions.keys())

    async def get_descriptions(self) -> dict[str, str]:
        """Return a dictionary of agent names and their descriptions."""
        descriptions = {}

        for doc in await arun(self.db.all):
            descriptions[doc["name"]] = doc["description"]

        for name, doc in self.factories.items():
            descriptions[name] = doc["description"]

        return descriptions

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
