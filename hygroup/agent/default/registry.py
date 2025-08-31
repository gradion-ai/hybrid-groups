import asyncio
import json
from pathlib import Path
from typing import Any, Callable

import aiofiles

from hygroup.agent.base import Agent, AgentFactory, AgentRegistry
from hygroup.agent.default.agent import AgentSettings, DefaultAgent


class DefaultAgentRegistry(AgentRegistry):
    """Registry for agent configurations and agent factories.

    Agent configurations are persisted in `registry_path`, agent factories are kept in memory.

    **THIS IS A REFERENCE IMPLEMENTATION FOR EXPERIMENTATION, DO NOT USE IN PRODUCTION.**
    """

    def __init__(self, registry_path: Path | str = Path(".data", "agents", "registry.json")):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self._factories: dict[str, dict[str, Any]] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        if self.registry_path.exists():
            self._configs = json.loads(self.registry_path.read_text())
        else:
            self._configs = {}

    def create_agent(self, name: str, tools: list[Callable] | None = None) -> Agent:
        """Create an agent from config or factory registered under `name`."""
        if doc := self._factories.get(name):
            return doc["factory"]()

        doc = self.get_config(name)

        if doc is None:
            raise ValueError(f"No agent registered with name '{name}'")

        settings = AgentSettings.from_dict(doc["settings"])
        agent = DefaultAgent(name=name, settings=settings)

        if tools is not None:
            for tool in tools:
                agent.tool(tool)

        return agent

    def get_registered_names(self) -> set[str]:
        """Get the names of all registered agent configs and factories."""
        descriptions = self.get_descriptions()
        return set(descriptions.keys())

    def get_descriptions(self) -> dict[str, str]:
        """Return a dictionary of agent names and their descriptions."""
        descriptions = {}

        for name, doc in self._configs.items():
            descriptions[name] = doc["description"]

        for name, doc in self._factories.items():
            descriptions[name] = doc["description"]

        return descriptions

    def get_emoji(self, name: str) -> str | None:
        if factory_doc := self._factories.get(name):
            return factory_doc.get("emoji")

        if config_doc := self.get_config(name):
            return config_doc.get("emoji")

        return None

    def get_config(self, name: str) -> dict[str, Any] | None:
        """Get the agent configuration registered under `name`."""
        return self._configs.get(name)

    def get_configs(self) -> dict[str, dict[str, Any]]:
        """Get the configurations for all agents."""
        return self._configs.copy()

    async def add_config(
        self,
        name: str,
        description: str,
        settings: AgentSettings,
        emoji: str | None = None,
    ):
        """Register an agent configuration."""
        async with self._lock:
            # Check if name already exists
            if name in self._configs:
                raise ValueError(f"Agent with name '{name}' already exists")

            # Convert AgentSettings to dict for storage
            settings_dict = settings.to_dict()

            # Create document (no 'name' field since it's the key)
            doc = {
                "description": description,
                "settings": settings_dict,
                "emoji": emoji,
            }

            # Add to in-memory configs
            self._configs[name] = doc

            # Save to file
            await self._save_configs()

    async def update_config(
        self,
        name: str,
        description: str | None = None,
        settings: AgentSettings | None = None,
        emoji: str | None = None,
    ):
        """Update and existing agent configuration."""
        async with self._lock:
            if name not in self._configs:
                raise ValueError(f"No agent registered with name '{name}'")

            # Update in-memory config
            if description is not None:
                self._configs[name]["description"] = description
            if settings is not None:
                self._configs[name]["settings"] = settings.to_dict()
            if emoji is not None:
                self._configs[name]["emoji"] = emoji

            # Save to file
            await self._save_configs()

    async def remove_config(self, name: str):
        """Remove an agent configuration."""
        async with self._lock:
            if name not in self._configs:
                raise ValueError(f"No agent registered with name '{name}'")

            # Remove from in-memory configs
            del self._configs[name]

            # Save to file
            await self._save_configs()

    async def remove_configs(self):
        """Remove all agent configurations."""
        async with self._lock:
            # Clear in-memory configs
            self._configs.clear()

            # Write empty dict to file
            async with aiofiles.open(self.registry_path, "w") as f:
                await f.write(json.dumps({}, indent=2))

    async def _save_configs(self):
        """Save the entire configs dict to the registry file."""
        async with aiofiles.open(self.registry_path, "w") as f:
            await f.write(json.dumps(self._configs, indent=2))

    def add_factory(self, name: str, description: str, factory: AgentFactory, emoji: str | None = None):
        self._factories[name] = {"name": name, "description": description, "factory": factory, "emoji": emoji}

    def remove_factory(self, name: str):
        self._factories.pop(name)

    def remove_factories(self):
        self._factories.clear()
