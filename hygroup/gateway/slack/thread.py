import asyncio
import io
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import aiofiles
import aiofiles.os
import aiohttp
from group_genie.agent import AgentFactory
from group_genie.message import Attachment
from group_genie.utils import arun
from PIL import Image

from hygroup.agent import PermissionRequest
from hygroup.gateway import AgentUpdate
from hygroup.gateway.slack.utils import BurstBuffer
from hygroup.session import Session


@dataclass
class SlackThread:
    channel_id: str
    session: Session
    permission_requests: dict[str, PermissionRequest] = field(default_factory=dict)
    wip_message_ids: dict[str, str] = field(default_factory=dict)
    wip_update_buffers: dict[str, BurstBuffer[AgentUpdate]] = field(default_factory=dict)
    response_upd: dict[str, asyncio.Task] = field(default_factory=dict)
    lock: asyncio.Lock = asyncio.Lock()

    @property
    def id(self) -> str:
        return self.session.id

    @property
    def agent_factory(self) -> AgentFactory:
        return self.session.agent_factory

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


async def download_attachment(file, target_dir: Path, max_image_size: int = 1024) -> Attachment:
    mimetype = file.get("mimetype", "application/octet-stream")
    filetype = file.get("filetype", "bin")
    name = file.get("name", "")

    download_url = file.get("url_private_download")

    attachment_id = uuid.uuid5(uuid.NAMESPACE_URL, download_url).hex[:8]
    attachment_path = target_dir / f"attachment-{attachment_id}.{filetype}"
    attachment = Attachment(path=str(attachment_path), name=name, media_type=mimetype)

    if await aiofiles.os.path.exists(attachment_path):
        return attachment

    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"}
        async with session.get(download_url, headers=headers) as response:
            response.raise_for_status()

            if mimetype.startswith("image/"):
                image_bytes = await response.content.read()
                with Image.open(io.BytesIO(image_bytes)) as img:
                    img.thumbnail((max_image_size, max_image_size), resample=Image.Resampling.LANCZOS)
                    await arun(img.save, attachment_path)
            else:
                async with aiofiles.open(attachment_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

        return attachment
