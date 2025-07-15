from abc import ABC, abstractmethod
from asyncio import Future
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Sequence


@dataclass
class Thread:
    session_id: str
    messages: list["Message"]


@dataclass
class Message:
    sender: str
    receiver: str | None
    text: str
    threads: list[Thread] = field(default_factory=list)
    handoffs: dict[str, str] | None = None
    id: str | None = None


@dataclass
class AgentRequest(ABC):
    query: str
    sender: str
    threads: list[Thread] = field(default_factory=list)
    id: str | None = None


@dataclass
class AgentResponse(ABC):
    text: str
    final: bool
    handoffs: dict[str, str] = field(default_factory=dict)


@dataclass
class PermissionRequest:
    tool_name: str
    tool_args: tuple
    tool_kwargs: dict[str, Any]
    ftr: Future

    # Set to True by an agent if the tool is an MCP
    # tool, executed by a user with its own secrets.
    as_user: bool = False

    # Snapshot of the number of agent responses in session
    _num_agent_responses: int = field(default=0, init=False)

    @property
    def call(self) -> str:
        args_str = ", ".join([repr(arg) for arg in self.tool_args])
        kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in self.tool_kwargs.items()])
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        return f"{self.tool_name}({all_args})"

    async def response(self) -> int:
        return await self.ftr

    def respond(self, granted: int | bool):
        self.ftr.set_result(granted)

    def deny(self):
        self.respond(0)

    def grant_once(self):
        self.respond(1)

    def grant_session(self):
        self.respond(2)

    def grant_always(self):
        self.respond(3)


@dataclass
class FeedbackRequest:
    question: str
    ftr: Future

    async def response(self) -> str:
        return await self.ftr

    def respond(self, text: str):
        self.ftr.set_result(text)


class Agent(ABC):
    def __init__(self, name: str):
        self.name = name

    @asynccontextmanager
    async def session_scope(self):
        yield

    @asynccontextmanager
    async def request_scope(self, secrets: dict[str, str] | None = None):
        yield

    @abstractmethod
    def run(
        self,
        request: AgentRequest,
        updates: Sequence[Message] = (),
        stream: bool = False,
    ) -> AsyncIterator[AgentResponse | PermissionRequest | FeedbackRequest]: ...

    @abstractmethod
    def get_state(self) -> Any: ...

    @abstractmethod
    def set_state(self, state: Any): ...


class AgentRegistry(ABC):
    @abstractmethod
    async def create_agent(self, name: str) -> Agent: ...

    @abstractmethod
    async def get_registered_names(self) -> set[str]: ...

    @abstractmethod
    async def get_descriptions(self) -> dict[str, str]: ...

    @abstractmethod
    async def get_emoji(self, name: str) -> str | None: ...

    async def get_registered_agents(self) -> str:
        """Get a list of registered agents in the format:

        - [agent name 1]: [agent description 1]
        - [agent name 2]: [agent description 2]
        - ...

        Returns:
            A string with the list of registered agents.
        """

        configs = await self.get_descriptions()
        return "\n".join([f"- {name}: {description}" for name, description in configs.items()])
