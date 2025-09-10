import re
from abc import ABC, abstractmethod

from hygroup.agent import FeedbackRequest, PermissionRequest


class UserNotAuthenticatedError(Exception):
    """Raised when accessing a resource that requires an authenticated user."""


class RequestHandler(ABC):
    @abstractmethod
    async def handle_permission_request(
        self,
        request: PermissionRequest,
        sender: str,
        receiver: str,
        session_id: str,
    ): ...

    @abstractmethod
    async def handle_feedback_request(
        self,
        request: FeedbackRequest,
        sender: str,
        receiver: str,
        session_id: str,
    ): ...


class PermissionStore(ABC):
    @abstractmethod
    async def get_permission(self, tool_name: str, username: str, session_id: str) -> int | None: ...

    @abstractmethod
    async def set_permission(self, tool_name: str, username: str, session_id: str, permission: int): ...


class CommandStore(ABC):
    COMMAND_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    @abstractmethod
    async def save_command(self, command: str, command_name: str, username: str): ...

    @abstractmethod
    async def load_command(self, command_name: str, username: str): ...

    @abstractmethod
    async def delete_command(self, command_name: str, username: str): ...

    @abstractmethod
    async def command_names(self, username: str) -> list[str]: ...
