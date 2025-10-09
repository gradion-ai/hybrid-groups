import io
import os
import uuid
from pathlib import Path

import aiofiles
import aiofiles.os
import aiohttp
from hylabs.message import Attachment
from hylabs.utils import arun
from PIL import Image


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
