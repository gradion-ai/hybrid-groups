from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class GatewayNotification(ABC):
    sender: str
    receiver: str
    session_id: str
    request_id: str | None


@dataclass
class MessageAck(GatewayNotification):
    pass


@dataclass
class MessageIgnore(GatewayNotification):
    pass


@dataclass
class AgentActivation(GatewayNotification):
    pass


@dataclass
class AgentUpdate(GatewayNotification):
    tool_name: str
    tool_kwargs: dict[str, Any]


@dataclass
class AgentResponse(GatewayNotification):
    text: str
    final: bool = True


class Gateway(ABC):
    @abstractmethod
    async def start(self, join: bool = True): ...

    @abstractmethod
    async def handle_message_ack(self, notification: MessageAck): ...

    @abstractmethod
    async def handle_message_ignore(self, notification: MessageIgnore): ...

    @abstractmethod
    async def handle_agent_activation(self, notification: AgentActivation): ...

    @abstractmethod
    async def handle_agent_update(self, notification: AgentUpdate): ...

    @abstractmethod
    async def handle_agent_response(self, notification: AgentResponse): ...
