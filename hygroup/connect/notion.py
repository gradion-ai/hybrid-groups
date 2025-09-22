import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import aiofiles
import aiohttp
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from hygroup.connect.utils import CallbackServer, InMemoryTokenStorage, handle_redirect
from hygroup.user.secrets import SecretsStore

logger = logging.getLogger(__name__)


@dataclass
class NotionAuthData:
    client_id: str
    client_secret: str
    refresh_token: str
    access_token: str
    access_token_expires_at: float

    async def save(self, path: Path):
        async with aiofiles.open(path, mode="w") as f:
            await f.write(json.dumps(asdict(self), indent=2))

    @classmethod
    async def load(cls, path: Path):
        async with aiofiles.open(path, mode="r") as f:
            return cls(**json.loads(await f.read()))


class NotionAuth:
    def __init__(self, root_path: Path = Path(".data", "users")):
        self.root_path = root_path
        self.base_url = "https://mcp.notion.com"
        self.refresh_tasks: dict[str, asyncio.Task] = {}

    @property
    def server_url(self) -> str:
        return f"{self.base_url}/mcp"

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/token"

    def auth_data_path(self, username: str) -> Path:
        return self.root_path / username / "notion.json"

    async def authorize(self, username: str):
        auth_data = await self._authorize()
        await auth_data.save(self.auth_data_path(username))

    async def _authorize(self) -> NotionAuthData:
        server = CallbackServer()
        storage = InMemoryTokenStorage()
        provider = OAuthClientProvider(
            server_url=self.server_url,
            client_metadata=OAuthClientMetadata(
                client_name="Notion MCP Client",
                redirect_uris=[AnyUrl(server.url())],
                grant_types=[
                    "authorization_code",
                    "refresh_token",
                ],
                response_types=["code"],
                scope="user",
            ),
            storage=storage,
            redirect_handler=handle_redirect,
            callback_handler=server.handle,
        )

        async with streamablehttp_client(self.server_url, auth=provider) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

        assert storage.tokens is not None
        assert storage.client_info is not None

        if storage.tokens.expires_in is None:
            storage.tokens.expires_in = 3600

        return NotionAuthData(
            client_id=storage.client_info.client_id,
            client_secret=storage.client_info.client_secret,
            refresh_token=storage.tokens.refresh_token,
            access_token=storage.tokens.access_token,
            access_token_expires_at=time.time() + storage.tokens.expires_in,
        )

    async def refresh_task(self, secrets_store: SecretsStore | None = None):
        for auth_data_path in self.root_path.glob("*/notion.json"):
            username = auth_data_path.parent.name
            task = asyncio.create_task(self._refresh_task(username, secrets_store))
            self.refresh_tasks[username] = task

    async def _refresh_task(self, username: str, secrets_store: SecretsStore | None = None):
        while True:
            auth_data_path = self.auth_data_path(username)
            auth_data = await NotionAuthData.load(auth_data_path)

            # Calculate when to refresh (5 minutes before expiration)
            refresh_time = auth_data.access_token_expires_at - 300
            current_time = time.time()

            # If the refresh time hasn't been reached yet, sleep until then
            if current_time < refresh_time:
                sleep_duration = refresh_time - current_time
                await asyncio.sleep(sleep_duration)

            # Refresh and save the updated access and refresh token
            auth_data = await self._refresh(auth_data=auth_data)
            await auth_data.save(auth_data_path)

            if secrets_store is not None:
                # Add the Notion access token to the user's secrets
                await secrets_store.set_secret(username, "NOTION_ACCESS_TOKEN", auth_data.access_token)

    async def refresh(self, username: str):
        auth_data_path = self.auth_data_path(username)
        auth_data = await NotionAuthData.load(auth_data_path)
        auth_data = await self._refresh(auth_data=auth_data)
        await auth_data.save(auth_data_path)

    async def _refresh(self, auth_data: NotionAuthData) -> NotionAuthData:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": auth_data.refresh_token,
                    "client_id": auth_data.client_id,
                    "client_secret": auth_data.client_secret,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ) as response:
                response_dict = await response.json()

        if "error" in response_dict:
            msg = f"Notion access token refresh for client id {auth_data.client_id} failed:"
            res = json.dumps(response_dict, indent=2)
            logger.error(f"{msg}\n{res}")
            # Keep current tokens and set retry a refresh in 30 seconds from now
            return replace(auth_data, access_token_expires_at=time.time() + 30)

        logger.info(f"Notion access token refreshed for client id {auth_data.client_id}")

        return replace(
            auth_data,
            refresh_token=response_dict["refresh_token"],
            access_token=response_dict["access_token"],
            access_token_expires_at=time.time() + response_dict["expires_in"],
        )
