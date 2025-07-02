from abc import ABC, abstractmethod

from hygroup.agent import AgentResponse


class Gateway(ABC):
    @abstractmethod
    async def start(self, join: bool = True): ...

    async def handle_selector_activation(self, message_id: str, session_id: str):
        pass

    async def handle_agent_activation(self, message_id: str, session_id: str):
        pass

    @abstractmethod
    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str): ...
