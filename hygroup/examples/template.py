import textwrap
from pathlib import Path

import aiofiles


class InstructionsTemplate:
    def __init__(self, template: str):
        self.template = template

    @staticmethod
    async def load(path: Path | None = None) -> "InstructionsTemplate":
        path = path or Path(__file__).parent / "template.md"

        async with aiofiles.open(path, "r") as f:
            return InstructionsTemplate(await f.read())

    def apply(self, agent_role: str, agent_steps: str) -> str:
        return self.template.format(
            role_description=agent_role,
            agent_specific_steps=textwrap.indent(agent_steps, "  "),
        )
