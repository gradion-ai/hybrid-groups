import json
import os
import uuid
from pathlib import Path
from typing import Any

import aiofiles
from composio_client import AsyncComposio

from hygroup.user import User, UserRegistry


class ComposioConfig:
    def __init__(self, data: dict[str, Any] | None = None):
        self._data = data or {}

    def add(self, name: str, auth_config_id: str, mcp_config_id: str, display_name: str):
        self._data[name] = {
            "auth_config_id": auth_config_id,
            "mcp_config_id": mcp_config_id,
            "display_name": display_name,
        }

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def toolkit_names(self) -> list[str]:
        return list(self._data.keys())

    def auth_config_id(self, toolkit_name: str) -> str:
        return self._data[toolkit_name]["auth_config_id"]

    def mcp_config_id(self, toolkit_name: str) -> str:
        return self._data[toolkit_name]["mcp_config_id"]

    def display_name(self, toolkit_name: str) -> str:
        return self._data[toolkit_name]["display_name"]

    def auth_config_ids(self) -> list[str]:
        return [item["auth_config_id"] for item in self._data.values()]

    def mcp_config_ids(self) -> list[str]:
        return [item["mcp_config_id"] for item in self._data.values()]

    def mcp_config_vars(self) -> dict[str, str]:
        vars = {}

        for toolkit_name in self.toolkit_names():
            vars[f"COMPOSIO_{toolkit_name.upper()}_ID"] = self.mcp_config_id(toolkit_name)

        return vars


class ComposioConnector:
    def __init__(
        self,
        user_registry: UserRegistry,
        config_path: Path = Path(".data", "composio", "config.json"),
        toolkits_path: Path | None = None,
        api_key: str | None = None,
    ):
        self.user_registry = user_registry
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.toolkits_path = toolkits_path if toolkits_path is not None else Path(__file__).parent / "toolkits.json"
        self.client = AsyncComposio(api_key=api_key or os.getenv("COMPOSIO_API_KEY"))

    async def save_config(self, config: ComposioConfig):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(self.config_path, "w") as f:
            await f.write(json.dumps(config.data, indent=2))

    async def load_config(self) -> ComposioConfig:
        if not self.config_path.exists():
            return ComposioConfig()

        async with aiofiles.open(self.config_path, "r") as f:
            return ComposioConfig(json.loads(await f.read()))

    async def tools(self, toolkit: str, include_deprecated: bool = False) -> dict[str, str]:
        tools = await self.client.tools.list(toolkit_slug=toolkit, limit=1000, include_deprecated=include_deprecated)
        return {item.slug: item.description for item in tools.items}

    async def setup(self):
        if self.config_path.exists():
            config = await self.load_config()
            data = config.data.copy()
        else:
            data = {}

        async with aiofiles.open(self.toolkits_path, "r") as f:
            toolkits = json.loads(await f.read())

        for name, value in toolkits.items():
            if name not in data:
                data[name] = await self._setup_toolkit(name, value)

        await self.save_config(ComposioConfig(data))

    async def cleanup(self):
        _config = await self.load_config()

        for mcp_config_id in _config.mcp_config_ids():
            await self.client.mcp.delete(id=mcp_config_id)

        for auth_config_id in _config.auth_config_ids():
            await self.client.auth_configs.delete(nanoid=auth_config_id)

        await self.save_config(ComposioConfig())

    async def connection_status(self, system_user_id: str, config: ComposioConfig | None = None) -> dict[str, bool]:
        # -----------------------------------------------------
        #  TODO: lock for atomic execution
        # -----------------------------------------------------
        _config = config or await self.load_config()

        if user_id := await self._get_composio_user_id(system_user_id):
            active_connections = await self._active_connections(user_id, _config)
        else:
            active_connections = []

        result = {}

        for toolkit_name in _config.toolkit_names():
            result[toolkit_name] = toolkit_name in active_connections

        return result

    async def connect_toolkit(self, system_user_id: str, toolkit_name: str) -> str:
        # -----------------------------------------------------
        #  TODO: lock for atomic execution
        # -----------------------------------------------------
        composio_user_id = await self._get_composio_user_id(system_user_id)

        if composio_user_id is None:
            composio_user_id = str(uuid.uuid4())
            await self._set_composio_user_id(system_user_id, composio_user_id)

        return await self._connect_toolkit(composio_user_id, toolkit_name)

    async def _setup_toolkit(self, name: str, value: dict[str, Any]) -> dict[str, str]:
        ac_response = await self.client.auth_configs.create(
            toolkit={"slug": name},
            auth_config={
                "name": f"hygroup-{name}",
                "type": "use_composio_managed_auth",
                "authScheme": "OAUTH2",
            },
        )

        mcp_response = await self.client.mcp.create(
            auth_config_ids=[ac_response.auth_config.id],
            name=f"hygroup-{name}",
            allowed_tools=value["tools"],
            managed_auth_via_composio=False,
        )

        return {
            "auth_config_id": ac_response.auth_config.id,
            "mcp_config_id": mcp_response.id,
            "display_name": value["display_name"],
        }

    async def _active_connections(self, composio_user_id: str, config: ComposioConfig) -> list[str]:
        """Return a list of toolkit names for which the given user has an active connection."""

        accounts = await self.client.connected_accounts.list(
            limit=100,
            user_ids=[composio_user_id],
            auth_config_ids=config.auth_config_ids(),
            toolkit_slugs=config.toolkit_names(),
        )

        connected = []
        for account in accounts.items:
            if account.status == "ACTIVE":
                connected.append(account.toolkit.slug)

        return connected

    async def _connect_toolkit(self, composio_user_id: str, toolkit_name: str) -> str:
        """Create a connected account for that user and toolkit,
        deleting existing accounts, and return the redirect URL.
        """
        config = await self.load_config()

        if toolkit_name not in config.data:
            raise ValueError(f"Toolkit {toolkit_name} not found in config")

        auth_config_id = config.auth_config_id(toolkit_name)

        accounts = await self.client.connected_accounts.list(
            limit=100,
            user_ids=[composio_user_id],
            auth_config_ids=[auth_config_id],
            toolkit_slugs=[toolkit_name],
        )
        for account in accounts.items:
            await self.client.connected_accounts.delete(account.id)

        response = await self.client.connected_accounts.create(
            auth_config={"id": auth_config_id},
            connection={"user_id": composio_user_id},
        )
        return response.connection_data.val.redirect_url

    async def _get_composio_user_id(self, system_user_id: str) -> str | None:
        if self.user_registry.get_user(system_user_id):
            if secrets := self.user_registry.get_secrets(system_user_id):
                if composio_user_id := secrets.get("COMPOSIO_USER_ID"):
                    return composio_user_id
        return None

    async def _set_composio_user_id(self, system_user_id: str, composio_user_id: str):
        if self.user_registry.get_user(system_user_id):
            await self.user_registry.set_secret(system_user_id, "COMPOSIO_USER_ID", composio_user_id)
        else:
            user = User(name=system_user_id, secrets={"COMPOSIO_USER_ID": composio_user_id})
            await self.user_registry.register(user)
