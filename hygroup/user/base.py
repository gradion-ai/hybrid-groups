from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from hygroup.agent import AgentSelectionConfirmationRequest, FeedbackRequest, PermissionRequest


class UserNotAuthenticatedError(Exception):
    """Raised when accessing a resource that requires an authenticated user."""


@dataclass
class User:
    name: str
    """The username."""

    secrets: dict[str, str] = field(default_factory=dict)
    """The secrets for the user. The key is the secret name, the value is the secret value."""

    mappings: dict[str, str] = field(default_factory=dict)
    """The gateway mappings for the user. The key is the gateway name, the value is the gateway username."""


class UserRegistry(ABC):
    @abstractmethod
    async def register(self, user: User, password: str | None): ...

    @abstractmethod
    def authenticate(self, username: str, password: str) -> bool: ...

    @abstractmethod
    def deauthenticate(self, username: str) -> bool: ...

    @abstractmethod
    def authenticated(self, username: str) -> bool: ...

    @abstractmethod
    def get_secrets(self, username: str) -> dict[str, str] | None: ...

    @abstractmethod
    def get_mappings(self, gateway: str) -> dict[str, str]: ...


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

    @abstractmethod
    async def handle_confirmation_request(
        self,
        request: AgentSelectionConfirmationRequest,
        sender: str,
        receiver: str,
        session_id: str,
    ): ...


class PermissionStore(ABC):
    @abstractmethod
    async def get_permission(self, tool_name: str, username: str, session_id: str) -> int | None: ...

    @abstractmethod
    async def set_permission(self, tool_name: str, username: str, session_id: str, permission: int): ...
