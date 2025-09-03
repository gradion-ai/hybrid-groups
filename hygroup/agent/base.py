import uuid
from abc import ABC, abstractmethod
from asyncio import Future
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Sequence

import aiofiles


@dataclass
class Attachment:
    path: str
    name: str
    media_type: str

    async def bytes(self) -> bytes:
        async with aiofiles.open(self.path, "rb") as f:
            return await f.read()


@dataclass
class Thread:
    session_id: str
    messages: list["Message"]

    @staticmethod
    def from_dicts(message_dicts: list[dict[str, Any]]) -> list["Message"]:
        """Convert a list of message dictionaries to Message objects."""
        messages = []
        for message_dict in message_dicts:
            message = Message.from_dict(message_dict)
            messages.append(message)
        return messages


@dataclass
class Message:
    text: str
    sender: str
    receiver: str | None
    threads: list[Thread] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)

    id: str | None = None
    """Id of the gateway message represented by this message."""

    @staticmethod
    def from_dict(message_dict: dict[str, Any]) -> "Message":
        """Convert a message dictionary to a Message object, recursively handling nested threads."""
        # message_data = message_dict.copy()
        message_data = message_dict
        if "threads" in message_data and message_data["threads"]:
            nested_threads = []
            for thread_data in message_data["threads"]:
                thread_messages = Thread.from_dicts(thread_data.get("messages", []))
                nested_thread = Thread(session_id=thread_data.get("session_id", ""), messages=thread_messages)
                nested_threads.append(nested_thread)
            message_data["threads"] = nested_threads
        return Message(**message_data)


@dataclass
class AgentRequest:
    query: str
    sender: str
    receiver: str | None = None
    threads: list[Thread] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    preferences: str | None = None
    """Sender preferences."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Id of this request."""
    message_id: str | None = None
    """Id of the gateway message that triggered this request."""


@dataclass
class AgentActivation:
    agent_name: str

    message_id: str | None = None
    """Id of the gateway message that activated agent."""
    request_id: str | None = None
    """Id of the request that activated agent."""


@dataclass
class AgentResponse:
    text: str
    final: bool = True

    message_id: str | None = None
    """Id of the gateway message that activated agent."""
    request_id: str | None = None
    """Id of the request that triggered this response."""


@dataclass
class PermissionRequest:
    tool_name: str
    tool_args: tuple
    tool_kwargs: dict[str, Any]
    ftr: Future

    # Set to True by an agent if the tool is an MCP
    # tool, executed by a user with its own secrets.
    as_user: bool = False

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
    async def mcp_servers(self, secrets: dict[str, str] | None = None):
        yield

    @abstractmethod
    def run(
        self,
        request: AgentRequest,
        updates: Sequence[Message] = (),
    ) -> AsyncIterator[AgentResponse | PermissionRequest | FeedbackRequest]: ...

    @abstractmethod
    def get_state(self) -> Any: ...

    @abstractmethod
    def set_state(self, state: Any): ...


AgentFactory = Callable[[], Agent]
