import asyncio
from dataclasses import dataclass, field

from hylabs.agent.registry import AgentRegistry

from hygroup.agent import PermissionRequest
from hygroup.gateway.slack.utils import download_attachment
from hygroup.session import Session


@dataclass
class SlackThread:
    channel_id: str
    session: Session
    permission_requests: dict[str, PermissionRequest] = field(default_factory=dict)
    response_ids: dict[str, str] = field(default_factory=dict)
    response_upd: dict[str, asyncio.Task] = field(default_factory=dict)
    lock: asyncio.Lock = asyncio.Lock()

    @property
    def id(self) -> str:
        return self.session.id

    @property
    def agent_registry(self) -> AgentRegistry:
        return self.session.agent_registry

    async def handle_message(self, msg: dict):
        sender = msg["sender"]

        attachments_dir = self.session.session_factory.data_store.narrow_path(self.id, sender)
        attachments_dir.mkdir(parents=True, exist_ok=True)
        attachments = []

        for file in msg.get("files") or []:
            attachment = await download_attachment(file, target_dir=attachments_dir)
            attachments.append(attachment)

        await self.session.handle(
            text=msg["text"],
            sender=sender,
            attachments=attachments,
            request_id=msg["id"],
        )
