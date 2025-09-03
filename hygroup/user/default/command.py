from pathlib import Path

import aiofiles
import aiofiles.os

from hygroup.user.base import CommandStore


class DefaultCommandStore(CommandStore):
    def __init__(self, root_dir: Path = Path(".data", "users", "commands")):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    async def save_command(self, command: str, command_name: str, username: str) -> None:
        # Validate command name - only alphanumeric, underscore, and hyphen
        if not self.COMMAND_NAME_PATTERN.match(command_name):
            raise ValueError(
                f"Invalid command name: {command_name}. Only alphanumeric characters, underscores, and hyphens are allowed."
            )

        user_dir = self.root_dir / username
        user_dir.mkdir(parents=True, exist_ok=True)

        command_file = user_dir / f"{command_name}.md"
        async with aiofiles.open(command_file, mode="w") as f:
            await f.write(command)

    async def load_command(self, command_name: str, username: str) -> str:
        command_file = self.root_dir / username / f"{command_name}.md"

        if not await aiofiles.os.path.exists(command_file):
            raise KeyError(f"Command '{command_name}' not found for user '{username}'")

        async with aiofiles.open(command_file, mode="r") as f:
            return await f.read()

    async def delete_command(self, command_name: str, username: str) -> None:
        command_file = self.root_dir / username / f"{command_name}.md"

        if not await aiofiles.os.path.exists(command_file):
            raise KeyError(f"Command '{command_name}' not found for user '{username}'")

        await aiofiles.os.remove(command_file)

    async def command_names(self, username: str) -> list[str]:
        user_dir = self.root_dir / username

        if not await aiofiles.os.path.exists(user_dir):
            return []

        command_names = []
        for file_path in user_dir.glob("*.md"):
            command_names.append(file_path.stem)

        return command_names
