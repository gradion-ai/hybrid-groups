from abc import ABC, abstractmethod

from hygroup.agent import AgentResponse


class Gateway(ABC):
    @abstractmethod
    async def start(self, join: bool = True): ...

    @abstractmethod
    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str): ...

    async def handle_agent_activation(self, agent_name: str | None, message_id: str, session_id: str):
        pass
