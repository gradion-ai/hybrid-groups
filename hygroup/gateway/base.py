from abc import ABC, abstractmethod

from hygroup.agent import AgentActivation, AgentResponse, AgentUpdate


class Gateway(ABC):
    @abstractmethod
    async def start(self, join: bool = True): ...

    @abstractmethod
    async def handle_agent_response(
        self,
        response: AgentResponse,
        sender: str,
        receiver: str,
        session_id: str,
    ): ...

    @abstractmethod
    async def handle_agent_activation(
        self,
        activation: AgentActivation,
        sender: str,
        receiver: str,
        session_id: str,
    ): ...

    async def handle_agent_update(
        self,
        update: AgentUpdate,
        sender: str,
        receiver: str,
        session_id: str,
    ): ...
