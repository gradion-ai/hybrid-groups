import json
from pathlib import Path

import aiofiles


class UserMapping:
    def __init__(self, path: Path = Path(".data", "users", "mapping.json")):
        self.path = path

    async def load(self, gateway: str) -> dict[str, str]:
        try:
            async with aiofiles.open(self.path, "r") as f:
                data = json.loads(await f.read())
                return data.get(gateway, {})
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
