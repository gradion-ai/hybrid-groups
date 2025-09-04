import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from github import Auth, GithubIntegration

from hygroup.agent import (
    AgentActivation,
    AgentResponse,
)
from hygroup.gateway import Gateway
from hygroup.gateway.github.events import (
    GithubEvent,
    IssueCommentCreated,
    IssueOpened,
    PullRequestCommentCreated,
    PullRequestOpened,
    PullRequestReviewSubmitted,
    map_github_event,
)
from hygroup.gateway.github.service import GithubService
from hygroup.gateway.github.webhook.app import create_app
from hygroup.gateway.github.webhook.config import AppSettings
from hygroup.session import Session, SessionManager

logger = logging.getLogger(__name__)

RECEIVER_SEPARATOR = "/"


@dataclass
class GithubRepository:
    repository_id: int
    repository_full_name: str


@dataclass
class GithubIssue:
    issue_id: int
    issue_number: int


@dataclass
class GithubConversation:
    repository: GithubRepository
    issue: GithubIssue
    session: Session

    @property
    def id(self) -> str:
        return self.session.id


class GithubGateway(Gateway):
    def __init__(
        self,
        session_manager: SessionManager,
        github_app_id: int | None = None,
        github_app_installation_id: int | None = None,
        github_app_webhook_secret: str | None = None,
        github_app_webhook_port: int | None = None,
        github_app_private_key: str | None = None,
        github_app_username: str | None = None,
        user_mapping: dict[str, str] = {},
    ):
        github_app_id = github_app_id or int(os.environ["GITHUB_APP_ID"])
        github_app_installation_id = github_app_installation_id or int(os.environ["GITHUB_APP_INSTALLATION_ID"])
        github_app_private_key = github_app_private_key or Path(os.environ["GITHUB_APP_PRIVATE_KEY_PATH"]).read_text()
        github_app_username = github_app_username or os.environ["GITHUB_APP_USERNAME"]
        github_app_webhook_secret = github_app_webhook_secret or os.environ["GITHUB_APP_WEBHOOK_SECRET"]
        github_app_webhook_port = github_app_webhook_port or 8000

        self._session_manager = session_manager
        self._github_user_mapping = user_mapping
        self._system_user_mapping = {v: k for k, v in user_mapping.items()}

        self._github_app_username = github_app_username
        self._github_app_fullname = f"{github_app_username}[bot]"
        self._github_auth = Auth.AppAuth(github_app_id, github_app_private_key)
        self._github_integration = GithubIntegration(auth=self._github_auth)
        self._github_client = self._github_integration.get_github_for_installation(github_app_installation_id)
        self._github_service = GithubService(github_client=self._github_client)

        self._webhooks_app_settings = AppSettings(
            webhook_port=github_app_webhook_port,
            webhook_secret=github_app_webhook_secret,
        )
        self._webhooks_app = create_app(self._webhooks_app_settings, self._handle_github_event)
        self._webhooks_app_config = uvicorn.Config(
            self._webhooks_app,
            host="0.0.0.0",
            port=self._webhooks_app_settings.webhook_port,
            log_config=str(self._webhooks_app_settings.log_config_path),
            log_level=self._webhooks_app_settings.log_level.lower(),
            reload=False,
        )
        self._webhooks_app_server = uvicorn.Server(self._webhooks_app_config)
        self._conversations: dict[str, GithubConversation] = {}

    async def start(self, join: bool = True):
        serve_task = asyncio.create_task(self._webhooks_app_server.serve())
        if join:
            await serve_task

    def _resolve_system_user_id(self, github_user_id: str) -> str:
        return self._github_user_mapping.get(github_user_id, github_user_id)

    def _resolve_github_user_id(self, system_user_id: str) -> str:
        return self._system_user_mapping.get(system_user_id, system_user_id)

    def _resolve_mentions(self, text: str | None) -> str:
        """Finds all mentions in @username format and replace them with the resolved
        username (with @ preserved).
        """
        if text is None:
            return ""

        def resolve(match):
            username = match.group(1)
            username = self._remove_receiver_prefix(username)
            resolved = self._resolve_system_user_id(username)
            return "@" + resolved

        return re.sub(r"(?<!\w)@([/\w-]+)", resolve, text)

    def _resolve_issue_references(self, text: str, repository_full_name: str) -> str:
        owner, name = repository_full_name.split("/")

        def replace(match: re.Match[str]) -> str:
            issue_number = match.group(1)
            session_id = f"{owner}-{name}-{issue_number}"
            return f"thread:{session_id}"

        return re.sub(r"#(\d+)", replace, text)

    def _conversation_id(self, event: GithubEvent) -> str:
        return f"{event.repository_owner}-{event.repository_name}-{event.issue_number}"

    def _remove_receiver_prefix(self, receiver: str) -> str:
        prefix = f"{self._github_app_username}{RECEIVER_SEPARATOR}"
        if receiver.startswith(prefix):
            return receiver[len(prefix) :]
        return receiver

    async def _handle_github_event(self, event_type: str, payload: dict):
        event = map_github_event(event_type, payload)

        if event is None:
            logger.warning("Unknown event type (event_type='%s')", event_type)
            return

        match event:
            case IssueOpened() | PullRequestOpened() as opened_event:
                conversation_id = self._conversation_id(opened_event)

                session = self._session_manager.create_session(id=conversation_id)

                conversation = self._register_conversation(conversation_id, opened_event, session)

                if opened_event.description is not None:
                    await self._handle_conversation_message(
                        conversation,
                        message=opened_event.description,
                        username=opened_event.username,
                        message_id="issue-description",
                    )

            case IssueCommentCreated() | PullRequestCommentCreated() | PullRequestReviewSubmitted() as comment_event:
                if comment_event.comment is None:
                    logger.info("Skipping event as it has no comment (event='%s')", type(comment_event).__name__)
                    return

                conversation = await self._lookup_or_load_conversation(comment_event)  # type: ignore
                if conversation is None:
                    logger.warning("Conversation for issue not found (issue_number='%d')", comment_event.issue_number)
                    return

                if comment_event.username == self._github_app_fullname:
                    return

                message_id: str | None
                match comment_event:
                    case IssueCommentCreated() | PullRequestCommentCreated():
                        message_id = f"issue-comment__{comment_event.comment_id}"
                    case _:
                        message_id = None

                await self._handle_conversation_message(
                    conversation,
                    message=comment_event.comment,
                    username=comment_event.username,
                    message_id=message_id,
                )

            case _:
                logger.info("Unhandled event (event='%s')", event)
                return

    async def _handle_conversation_message(
        self, conversation: GithubConversation, message: str, username: str, message_id: str | None = None
    ):
        sender_resolved = self._resolve_system_user_id(username)

        # replace all @mentions in text with resolved usernames (preserving @)
        text = self._resolve_mentions(message)

        # translate issue references to thread references
        text = self._resolve_issue_references(text, conversation.repository.repository_full_name)

        logger.info(
            "Processing message (sender='%s', text='%s')",
            sender_resolved,
            text[:50] + "..." if len(text) > 50 else text,
        )

        await conversation.session.handle_gateway_message(
            text=text,
            sender=sender_resolved,
            message_id=message_id,
        )

    def _register_conversation(self, conversation_id: str, event: GithubEvent, session: Session) -> GithubConversation:
        session.set_gateway(self)
        session.sync()

        self._conversations[conversation_id] = GithubConversation(
            repository=GithubRepository(
                repository_id=event.repository_id,
                repository_full_name=event.repository_full_name,
            ),
            issue=GithubIssue(
                issue_id=event.issue_id,
                issue_number=event.issue_number,
            ),
            session=session,
        )
        return self._conversations[conversation_id]

    async def _lookup_or_load_conversation(self, event: GithubEvent) -> GithubConversation | None:
        conversation_id = self._conversation_id(event)

        if conversation := self._conversations.get(conversation_id):
            return conversation

        if session := await self._session_manager.load_session(id=conversation_id):
            return self._register_conversation(conversation_id, event, session)
        else:
            return None

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        logger.info(
            "Sending agent response (sender='%s', receiver='%s', text='%s')",
            sender,
            receiver,
            response.text[:50] + "..." if len(response.text) > 50 else response.text,
        )

        conversation = self._conversations.get(session_id)
        if conversation is None:
            logger.warning("Conversation for session not found (session_id='%s')", session_id)
            return

        emoji = "rocket" if response.text else "+1"

        if response.message_id == "issue-description":
            await self._github_service.add_reaction_to_issue_description(
                repository_name=conversation.repository.repository_full_name,
                issue_number=conversation.issue.issue_number,
                reaction=emoji,
            )
        elif response.message_id and response.message_id.startswith("issue-comment"):
            await self._github_service.add_reaction_to_issue_comment(
                repository_name=conversation.repository.repository_full_name,
                issue_number=conversation.issue.issue_number,
                comment_id=int(response.message_id.split("__")[1]),
                reaction=emoji,
            )

        if not response.text:
            return

        receiver_resolved = self._resolve_github_user_id(receiver)
        sender_resolved = self._resolve_github_user_id(sender)

        text = f"[{sender_resolved}] " if sender_resolved != self._github_app_username else ""
        text += f"@{receiver_resolved} {response.text}"

        await self._github_service.create_issue_comment(
            repository_name=conversation.repository.repository_full_name,
            issue_number=conversation.issue.issue_number,
            text=text,
        )

    async def handle_agent_activation(self, activation: AgentActivation, session_id: str):
        conversation = self._conversations.get(session_id)
        if conversation is None:
            logger.warning("Conversation for session not found (session_id='%s')", session_id)
            return

        if not activation.message_id:
            return

        emoji = "eyes"

        if activation.message_id == "issue-description":
            await self._github_service.add_reaction_to_issue_description(
                repository_name=conversation.repository.repository_full_name,
                issue_number=conversation.issue.issue_number,
                reaction=emoji,
            )
        elif activation.message_id.startswith("issue-comment"):
            await self._github_service.add_reaction_to_issue_comment(
                repository_name=conversation.repository.repository_full_name,
                issue_number=conversation.issue.issue_number,
                comment_id=int(activation.message_id.split("__")[1]),
                reaction=emoji,
            )
