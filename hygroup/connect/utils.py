import asyncio
import webbrowser

from aiohttp import web
from mcp.client.auth import TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from hygroup.utils import arun


class CallbackServer:
    def __init__(self, port: int = 8797, path: str = "/callback"):
        self.host = "localhost"
        self.port = port
        self.path = path

    def url(self) -> str:
        return f"http://{self.host}:{self.port}{self.path}"

    async def handle(self) -> tuple[str, str]:
        queue = asyncio.Queue()  # type: ignore

        async def handler(request):
            await queue.put((request.query["code"], request.query["state"]))
            return web.Response(text="Authorization successful")

        app = web.Application()
        app.router.add_get(self.path, handler)
        app_runner = web.AppRunner(app)
        await app_runner.setup()

        site = web.TCPSite(app_runner, self.host, self.port)
        await site.start()
        print(f"Callback server started at {self.url()}")

        code, state = await queue.get()

        await app_runner.cleanup()
        print("Callback server stopped")

        return code, state


class InMemoryTokenStorage(TokenStorage):
    def __init__(self):
        self.tokens = None
        self.client_info = None

    async def get_tokens(self) -> OAuthToken | None:
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.client_info = client_info


async def handle_redirect(auth_url):
    await arun(webbrowser.open, auth_url)
