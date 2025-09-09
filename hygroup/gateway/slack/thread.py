import asyncio
import os
from dataclasses import dataclass, field
from uuid import uuid4

import aiofiles
import aiohttp

from hygroup.agent import Attachment, PermissionRequest
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

        if files := msg.get("files"):
            attachments = await self._download_attachments(files)
        else:
            attachments = None

        await self.session.handle_gateway_message(
            text=msg["text"],
            sender=msg["sender"],
            message_id=msg["id"],
            attachments=attachments,
        )

    async def _download_attachments(self, files: list) -> list[Attachment] | None:
        root = self.session.root()

        headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
        result = []

        async with aiohttp.ClientSession() as session:
            for i, file in enumerate(files):
                mimetype = file.get("mimetype", "application/octet-stream")
                filetype = file.get("filetype", "bin")
                name = file.get("name", f"unknown_{i}.{filetype}")
                url_private_download = file.get("url_private_download")

                if not url_private_download:
                    continue

                attachment_id = uuid4().hex[:8]
                filename = f"attachment-{attachment_id}.{filetype}"
                target_path = root / filename

                async with session.get(url_private_download, headers=headers) as response:
                    response.raise_for_status()
                    async with aiofiles.open(target_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)

                attachment = Attachment(path=str(target_path), name=name, media_type=mimetype)
                result.append(attachment)

        return result
