import asyncio
import json
from pathlib import Path

import aiofiles
import aiofiles.os


class DefaultPreferenceStore:
    """Database for user preferences.

    **THIS IS A REFERENCE IMPLEMENTATION FOR EXPERIMENTATION, DO NOT USE IN PRODUCTION.**
    """

    def __init__(self, preferences_path: Path | str = Path(".data", "users", "preferences.json")):
        self.preferences_path = Path(preferences_path)
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def _read_data(self) -> dict[str, str]:
        """Read the preferences data from disk."""
        if not await aiofiles.os.path.exists(self.preferences_path):
            return {}

        async with aiofiles.open(self.preferences_path, mode="r") as f:
            content = await f.read()
            if not content:
                return {}
            return json.loads(content)

    async def _write_data(self, data: dict[str, str]) -> None:
        """Write the preferences data to disk."""
        async with aiofiles.open(self.preferences_path, mode="w") as f:
            await f.write(json.dumps(data, indent=2))

    async def get_preferences(self, username: str) -> str | None:
        async with self._lock:
            data = await self._read_data()
            return data.get(username)

    async def set_preferences(self, username: str, preferences: str) -> None:
        async with self._lock:
            data = await self._read_data()
            data[username] = preferences
            await self._write_data(data)

    async def delete_preferences(self, username: str) -> None:
        async with self._lock:
            data = await self._read_data()
            if username in data:
                del data[username]
                await self._write_data(data)
