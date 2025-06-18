import asyncio

from aioconsole import ainput, aprint

from hygroup.agent import AgentRequest, AgentResponse
from hygroup.gateway.base import Gateway
from hygroup.gateway.utils import extract_mention, format_response
from hygroup.session import SessionManager


class LocalTerminalGateway(Gateway):
    def __init__(self, session_manager: SessionManager, initial_agent_name: str, username: str):
        self.current_agent_name = initial_agent_name
        self.username = username

        self._session = session_manager.create_session()
        self._session.set_gateway(self)
        self._event = asyncio.Event()

    async def start(self, join: bool = True):
        asyncio.create_task(self.prompt())
        if join:
            await self._event.wait()

    async def stop(self):
        self._event.set()

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        self.current_agent_name = self.current_agent_name if sender == "system" else sender
        await aprint(f"Message from {self.current_agent_name} to {receiver}:")
        await aprint(format_response(response.text, response.handoffs))
        if not response.handoffs:
            asyncio.create_task(self.prompt())

    async def prompt(self):
        query = await ainput(f"Message from {self.username} to {self.current_agent_name} (or @mention another agent): ")
        if query == "exit":
            await self.stop()
        else:
            agent_name, query = extract_mention(query)
            await self._session.invoke(
                AgentRequest(query=query, sender=self.username), receiver=agent_name or self.current_agent_name
            )
