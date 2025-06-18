import logging
import uuid
from typing import Any, Dict

import aiohttp
from fastapi import HTTPException

from hygroup.setup.apps.models import (
    GitHubAppCredentials,
    GitHubAppManifest,
)

logger = logging.getLogger(__name__)


DEFAULT_PERMISSIONS = {
    "issues": "write",
    "pull_requests": "write",
    "metadata": "read",
}

DEFAULT_EVENTS = [
    "issue_comment",
    "issues",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "pull_request_review_thread",
]


class GitHubAppSetupService:
    def __init__(self):
        self._state: Dict[str, Dict[str, Any]] = {}

    def _store_state(self, state: str, data: Dict[str, Any]) -> None:
        self._state[state] = data

    def _validate_state(self, state: str) -> Dict[str, Any]:
        if state not in self._state:
            raise ValueError("Invalid or expired authorization link. Please try creating the GitHub App again.")
        return self._state.pop(state)

    def create_manifest(
        self,
        app_name: str,
        organization: str | None,
        webhook_url: str,
        host: str,
        port: int,
        callback_route: str,
    ) -> tuple[Dict[str, Any], str]:
        manifest = GitHubAppManifest(
            name=app_name,
            url="https://github.com/gradion-ai",
            hook_attributes={"url": webhook_url, "active": True},
            redirect_url=f"http://{host}:{port}{callback_route}",
            default_permissions=DEFAULT_PERMISSIONS,
            default_events=DEFAULT_EVENTS,
            public=True,
        )

        manifest_dict = manifest.model_dump()

        state = str(uuid.uuid4())

        self._store_state(
            state,
            {
                "manifest": manifest_dict,
                "organization": organization,
                "app_name": app_name,
            },
        )

        if organization:
            github_url = f"https://github.com/organizations/{organization}/settings/apps/new?state={state}"
        else:
            github_url = f"https://github.com/settings/apps/new?state={state}"

        return manifest_dict, github_url

    async def handle_github_callback(
        self,
        code: str,
        state: str,
    ) -> tuple[str, str | None, str, GitHubAppCredentials]:
        stored_data = self._validate_state(state)

        logger.info("Processing callback (app_name='%s')", stored_data["app_name"])

        credentials = await self._exchange_code_for_credentials(code)

        logger.info("Successfully retrieved credentials (app_id='%s')", credentials.app_id)

        installation_url = f"https://github.com/apps/{credentials.slug}/installations/new"

        return (
            stored_data["app_name"],
            stored_data["organization"],
            installation_url,
            credentials,
        )

    async def _exchange_code_for_credentials(self, code: str) -> GitHubAppCredentials:
        url = f"https://api.github.com/app-manifests/{code}/conversions"
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                if response.status != 201:
                    error_text = await response.text()
                    logger.error("GitHub API error (status='%s', error='%s')", response.status, error_text)
                    raise HTTPException(
                        status_code=500, detail=f"Failed to exchange code for credentials: {response.status}"
                    )

                data = await response.json()

                return GitHubAppCredentials(
                    app_id=data["id"],
                    slug=data["slug"],
                    client_secret=data["client_secret"],
                    webhook_secret=data["webhook_secret"],
                    pem=data["pem"],
                )
