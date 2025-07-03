import asyncio
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
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self._factories: dict[str, dict[str, Any]] = {}
        self._tinydb = TinyDB(str(self.registry_path), indent=2)
        self._lock = asyncio.Lock()

    async def create_agent(self, name: str) -> AgentBase:
        """Create an agent from config or factory registered under `name`."""
        if doc := self._factories.get(name):
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

        async with self._lock:
            for doc in await arun(self._tinydb.all):
                descriptions[doc["name"]] = doc["description"]

        for name, doc in self._factories.items():
            descriptions[name] = doc["description"]

        return descriptions

    async def get_emoji(self, name: str) -> str | None:
        if factory_doc := self._factories.get(name):
            return factory_doc.get("emoji")

        if config_doc := await self.get_config(name):
            return config_doc.get("emoji")

        return None

    async def get_config(self, name: str) -> dict[str, Any]:
        """Return the configuration for an agent."""
        Agent = Query()

        async with self._lock:
            return await arun(self._tinydb.get, Agent.name == name)

    async def add_config(
        self,
        name: str,
        description: str,
        settings: AgentSettings,
        handoff: bool = False,
        emoji: str | None = None,
    ):
        """Add settings for an agent."""
        Agent = Query()

        async with self._lock:
            # Check if name already exists
            existing = await arun(self._tinydb.get, Agent.name == name)
            if existing is not None:
                raise ValueError(f"Agent with name '{name}' already exists")

            # Convert AgentSettings to dict for storage
            settings_dict = settings.to_dict()

            # Create document
            doc = {
                "name": name,
                "description": description,
                "handoff": handoff,
                "settings": settings_dict,
                "emoji": emoji,
            }

            # Insert document
            await arun(self._tinydb.insert, doc)

    async def remove_config(self, name: str):
        """Remove settings for an agent."""
        Agent = Query()

        async with self._lock:
            removed_ids = await arun(self._tinydb.remove, Agent.name == name)

        if not removed_ids:
            raise ValueError(f"No agent registered with name '{name}'")

    async def remove_configs(self):
        async with self._lock:
            await arun(self._tinydb.drop_tables)

    def add_factory(self, name: str, description: str, factory: AgentFactory, emoji: str | None = None):
        self._factories[name] = {"name": name, "description": description, "factory": factory, "emoji": emoji}

    def remove_factory(self, name: str):
        self._factories.pop(name)

    def remove_factories(self):
        self._factories.clear()
