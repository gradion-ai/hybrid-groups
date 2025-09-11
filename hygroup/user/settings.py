import json
import re
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os


class CommandNotFoundError(Exception):
    def __init__(self, command_name: str):
        super().__init__(f"Command '{command_name}' not found")
        self.command_name = command_name


class SettingsStore:
    SAFE_NAME_PATTERN = r"^[a-zA-Z0-9_-]+$"

    def __init__(self, root_path: Path = Path(".data", "users"), allowed_tools: list[str] | None = None):
        self.root_path = root_path
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.allowed_tools = allowed_tools or [
            "run_agent",
            "ask_user",
            "final_result",
        ]
        self._permissions: dict[str, Any] = {}  # write-through cache
        self._preferences: dict[str, str | None] = {}  # write-through cache
        self._mappings: dict[str, dict[str, str]] = self._load_mappings()

    def _load_mappings(self) -> dict[str, dict[str, str]]:
        mapping_file = self.root_path / "mapping.json"
        return {} if not mapping_file.exists() else json.loads(mapping_file.read_text())

    def get_mapping(self, gateway: str) -> dict[str, str]:
        return self._mappings.get(gateway, {})

    async def get_command_names(self, username: str) -> list[str]:
        commands_dir = self._command_dir(username)
        if not await aiofiles.os.path.exists(commands_dir):
            return []

        command_names = []
        for item in commands_dir.iterdir():
            if item.is_file() and item.suffix == ".md":
                command_names.append(item.stem)

        return sorted(command_names)

    async def get_command(self, username: str, command_name: str) -> str:
        command_file = self._command_file(username, command_name)

        if not await aiofiles.os.path.exists(command_file):
            raise CommandNotFoundError(command_name)

        async with aiofiles.open(command_file, "r", encoding="utf-8") as f:
            return await f.read()

    async def set_command(self, username: str, command_name: str, command: str):
        # Validate command name - only alphanumeric, underscore, and hyphen
        if not re.match(self.SAFE_NAME_PATTERN, command_name):
            raise ValueError(
                f"Invalid command name: {command_name}. Only alphanumeric characters, underscores, and hyphens are allowed."
            )

        command_file = self._command_file(username, command_name)
        await aiofiles.os.makedirs(command_file.parent, exist_ok=True)

        # Atomic write using temp file
        temp_file = command_file.with_suffix(".tmp")
        async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
            await f.write(command)
        await aiofiles.os.replace(temp_file, command_file)

    async def delete_command(self, username: str, command_name: str):
        command_file = self._command_file(username, command_name)

        if await aiofiles.os.path.exists(command_file):
            await aiofiles.os.remove(command_file)

    async def get_preferences(self, username: str) -> str | None:
        if username in self._preferences:
            return self._preferences[username]

        # Load from file
        preferences_file = self._preferences_file(username)

        if not await aiofiles.os.path.exists(preferences_file):
            self._preferences[username] = None
            return None

        async with aiofiles.open(preferences_file, "r", encoding="utf-8") as f:
            content = await f.read()

        self._preferences[username] = content

        return content

    async def set_preferences(self, username: str, preferences: str):
        self._preferences[username] = preferences

        preferences_file = self._preferences_file(username)
        await aiofiles.os.makedirs(preferences_file.parent, exist_ok=True)

        # Atomic write using temp file
        temp_file = preferences_file.with_suffix(".tmp")
        async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
            await f.write(preferences)
        await aiofiles.os.replace(temp_file, preferences_file)

    async def delete_preferences(self, username: str):
        self._preferences[username] = None

        preferences_file = self._preferences_file(username)

        if await aiofiles.os.path.exists(preferences_file):
            await aiofiles.os.remove(preferences_file)

    async def get_permission(self, username: str, tool_name: str, session_id: str) -> bool:
        if tool_name in self.allowed_tools:
            return True

        if username not in self._permissions:
            await self._load_permissions(username)

        user_permissions = self._permissions.get(username)
        if not user_permissions:
            return False

        if tool_name in user_permissions.get("permanent", []):
            return True

        sessions = user_permissions.get("sessions", {})
        if session_id in sessions and tool_name in sessions[session_id]:
            return True

        return False

    async def set_permission(self, username: str, tool_name: str, session_id: str | None):
        if username not in self._permissions:
            await self._load_permissions(username)

        # Initialize user permissions if needed
        if username not in self._permissions or self._permissions[username] is None:
            self._permissions[username] = {"permanent": [], "sessions": {}}

        user_permissions = self._permissions[username]

        if session_id is None:
            # Add to permanent permissions
            if tool_name not in user_permissions["permanent"]:
                user_permissions["permanent"].append(tool_name)
        else:
            # Add to session permissions
            if session_id not in user_permissions["sessions"]:
                user_permissions["sessions"][session_id] = []
            if tool_name not in user_permissions["sessions"][session_id]:
                user_permissions["sessions"][session_id].append(tool_name)

        await self._save_permissions(username)

    async def _load_permissions(self, username: str):
        permissions_file = self._permissions_file(username)

        if not await aiofiles.os.path.exists(permissions_file):
            self._permissions[username] = None
            return

        async with aiofiles.open(permissions_file, "r", encoding="utf-8") as f:
            content = await f.read()

        self._permissions[username] = json.loads(content)

    async def _save_permissions(self, username: str):
        user_permissions = self._permissions[username]
        if not user_permissions:
            return

        permissions_file = self._permissions_file(username)
        await aiofiles.os.makedirs(permissions_file.parent, exist_ok=True)

        # Atomic write using temp file
        temp_file = permissions_file.with_suffix(".tmp")
        async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(user_permissions, indent=2))
        await aiofiles.os.replace(temp_file, permissions_file)

    def _command_dir(self, username: str) -> Path:
        return self.root_path / self._sanitize_username(username) / "commands"

    def _command_file(self, username: str, command_name: str) -> Path:
        return self._command_dir(username) / f"{command_name}.md"

    def _preferences_file(self, username: str) -> Path:
        return self.root_path / self._sanitize_username(username) / "preferences.md"

    def _permissions_file(self, username: str) -> Path:
        return self.root_path / self._sanitize_username(username) / "permissions.json"

    def _sanitize_username(self, username: str) -> str:
        if not username.strip():
            raise ValueError("Username cannot be empty")

        # Replace any character not in the safe pattern with underscore
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", username)
        return sanitized
