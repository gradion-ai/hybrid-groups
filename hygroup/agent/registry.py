import json
from pathlib import Path
from typing import Any, Callable

import aiofiles

from hygroup.agent.base import Agent, AgentFactory
from hygroup.agent.default import AgentSettings, DefaultAgent
from hygroup.agent.system import SystemAgent


class AgentRegistries:
    def __init__(self, root_path: Path = Path(".data", "agents")):
        self.root_path = root_path
        self.root_path.mkdir(parents=True, exist_ok=True)

        self._default_registry = AgentRegistry(root_path / "registry.json")
        self._custom_registries: dict[str, AgentRegistry] = {}

        for path in self.root_path.glob("*/registry.json"):
            self._custom_registries[path.parent.name] = AgentRegistry(path)

    def get_registry(self, name: str | None = None) -> "AgentRegistry":
        if name in self._custom_registries:
            return self._custom_registries[name]
        else:
            return self._default_registry


class AgentRegistry:
    """Registry for agent configurations and agent factories."""

    def __init__(self, registry_path: Path | str = Path(".data", "agents", "registry.json")):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self._factories: dict[str, dict[str, Any]] = {}
        self._configs: dict[str, dict[str, Any]] = {}

        if self.registry_path.exists():
            self._configs = json.loads(self.registry_path.read_text())
        else:
            self._configs = {}

    def create_agent(self, name: str, tools: list[Callable] | None = None) -> Agent:
        """Create an agent from config or factory registered under `name`."""
        if config := self._factories.get(name):
            return config["factory"]()

        config = self.get_config(name)

        if config is None:
            raise ValueError(f"No agent registered with name '{name}'")

        settings = AgentSettings.from_dict(config["settings"])

        if name == "system":
            agent = SystemAgent(
                settings=settings,
                registered_agents=self.get_registered_agents(),
            )
        else:
            agent = DefaultAgent(name=name, settings=settings)  # type: ignore

        if tools is not None:
            for tool in tools:
                agent.tool(tool)

        return agent

    def get_registered_agents(self) -> str | None:
        """Get a list of registered agents in the format:

        - [agent name 1]: [agent description 1]
        - [agent name 2]: [agent description 2]
        - ...

        Returns:
            A string with the list of registered agents.
        """
        descriptions = []

        for name, description in self.get_descriptions().items():
            if name != "system":
                descriptions.append(f"- {name}: {description}")

        if descriptions:
            return "\n".join(descriptions)

        return None

    def get_default_agent(self) -> str | None:
        """Get the name of the default agent."""
        for name, config in self._configs.items():
            if config.get("default"):
                return name
        return "system" if "system" in self._configs else None

    def get_registered_names(self) -> set[str]:
        """Get the names of all registered agent configs and factories."""
        descriptions = self.get_descriptions()
        return set(descriptions.keys())

    def get_descriptions(self) -> dict[str, str]:
        """Return a dictionary of agent names and their descriptions."""
        descriptions = {}

        for name, config in self._configs.items():
            descriptions[name] = config["description"]

        for name, config in self._factories.items():
            descriptions[name] = config["description"]

        return descriptions

    def get_emoji(self, name: str) -> str | None:
        if factory_config := self._factories.get(name):
            return factory_config.get("emoji")

        if config := self.get_config(name):
            return config.get("emoji")

        return None

    def get_config(self, name: str) -> dict[str, Any] | None:
        """Get the agent configuration registered under `name`."""
        return self._configs.get(name)

    def get_configs(self) -> dict[str, dict[str, Any]]:
        """Get the configurations for all agents."""
        return self._configs.copy()

    def add_config(
        self,
        name: str,
        description: str,
        settings: AgentSettings,
        emoji: str | None = None,
        default: bool | None = None,
    ):
        """Register an agent configuration in memory. Call save() to persist."""
        # Check if name already exists
        if name in self._configs:
            raise ValueError(f"Agent with name '{name}' already exists")

        # Convert AgentSettings to dict for storage
        settings_dict = settings.to_dict()

        config: dict[str, Any] = {
            "description": description,
            "settings": settings_dict,
            "emoji": emoji,
        }

        if default is not None:
            config["default"] = default

        # Add to in-memory configs
        self._configs[name] = config

    def update_config(
        self,
        name: str,
        description: str | None = None,
        settings: AgentSettings | None = None,
        emoji: str | None = None,
    ):
        """Update an existing agent configuration in memory. Call save() to persist."""
        if name not in self._configs:
            raise ValueError(f"No agent registered with name '{name}'")

        # Update in-memory config
        if description is not None:
            self._configs[name]["description"] = description
        if settings is not None:
            self._configs[name]["settings"] = settings.to_dict()
        if emoji is not None:
            self._configs[name]["emoji"] = emoji

    def remove_config(self, name: str):
        """Remove an agent configuration from memory. Call save() to persist."""
        if name not in self._configs:
            raise ValueError(f"No agent registered with name '{name}'")

        # Remove from in-memory configs
        del self._configs[name]

    def remove_configs(self):
        """Remove all agent configurations from memory. Call save() to persist."""
        # Clear in-memory configs
        self._configs.clear()

    async def save(self):
        """Save the entire configs dict to the registry file."""
        async with aiofiles.open(self.registry_path, "w") as f:
            await f.write(json.dumps(self._configs, indent=2))

    def add_factory(self, name: str, description: str, factory: AgentFactory, emoji: str | None = None):
        self._factories[name] = {"name": name, "description": description, "factory": factory, "emoji": emoji}

    def remove_factory(self, name: str):
        self._factories.pop(name)

    def remove_factories(self):
        self._factories.clear()
