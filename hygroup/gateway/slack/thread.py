import asyncio
from dataclasses import dataclass, field

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
    def channel_name(self) -> str | None:
        return self.session.channel

    async def handle_message(self, msg: dict):
        if self.session.contains(msg["id"]):
            return

        attachments = []
        for file in msg.get("files") or []:
            attachment = await download_attachment(file, self.session.root())
            attachments.append(attachment)

        await self.session.handle_gateway_message(
            text=msg["text"],
            sender=msg["sender"],
            message_id=msg["id"],
            attachments=attachments,
        )
