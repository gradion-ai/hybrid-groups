import asyncio
import html
import json
import logging
import os
import signal
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from hygroup.setup.apps.constants import Paths, Routes
from hygroup.setup.apps.credentials import CredentialManager
from hygroup.setup.apps.github import GitHubAppSetupService
from hygroup.setup.apps.models import (
    GitHubAppCreateRequest,
    GitHubCompleteRequest,
    GitHubCompleteResponse,
    GitHubManifestResponse,
    SlackAppCreateRequest,
    SlackAppCreateResponse,
    SlackCompleteRequest,
    SlackCompleteResponse,
)
from hygroup.setup.apps.slack import (
    SlackAppSetupService,
)

logger = logging.getLogger(__name__)


def create_app(
    host: str,
    port: int,
    credential_manager: CredentialManager,
):
    github_app_setup_service = GitHubAppSetupService()
    slack_app_setup_service = SlackAppSetupService()

    app = FastAPI(title="App Setup Service")

    app.mount("/static", StaticFiles(directory=str(Paths.STATIC)), name="static")

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return await _render_error_page(str(exc), status_code=400)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc)
        return await _render_error_page("An unexpected error occurred", status_code=500)

    @app.get(Routes.GITHUB_APP)
    async def serve_github_app():
        return FileResponse(str(Paths.SETUP_GITHUB_TEMPLATE))

    @app.post(Routes.GITHUB_MANIFEST, response_model=GitHubManifestResponse)
    async def create_manifest(request: GitHubAppCreateRequest):
        manifest, github_url = await github_app_setup_service.create_manifest(
            app_name=request.app_name,
            organization=request.organization,
            host=host,
            port=port,
            callback_route=Routes.GITHUB_CALLBACK,
        )
        return GitHubManifestResponse(manifest=manifest, github_url=github_url)

    @app.get(Routes.GITHUB_CALLBACK)
    async def handle_callback(
        code: str = Query(..., description="Authorization code from GitHub"),
        state: str = Query(..., description="State parameter for CSRF protection"),
    ):
        (
            app_name,
            organization,
            installation_url,
            webhook_url,
            credentials,
        ) = await github_app_setup_service.handle_github_callback(code, state)

        private_key_path, env_file_path = await credential_manager.save_github_credentials(
            credentials, organization, webhook_url
        )

        logger.info(
            "Saved credentials (app_name='%s', slug='%s', private_key_path='%s', env_file_path='%s')",
            app_name,
            credentials.slug,
            str(private_key_path),
            str(env_file_path),
        )

        # Redirect back to the wizard with success parameters
        from urllib.parse import urlencode

        from fastapi.responses import RedirectResponse

        redirect_params = {
            "setup": "complete",
            "app_id": str(credentials.app_id),
            "app_slug": credentials.slug,
            "app_name": app_name,
            "installation_url": installation_url,
            "webhook_url": webhook_url,
        }

        redirect_url = f"/github-app?{urlencode(redirect_params)}"
        return RedirectResponse(url=redirect_url, status_code=302)

    @app.post(Routes.GITHUB_COMPLETE, response_model=GitHubCompleteResponse)
    async def complete_registration(request: GitHubCompleteRequest):
        """Complete the GitHub App registration process"""
        installation_id_saved = False

        if request.installation_id:
            credential_manager.append_github_installation_id(request.installation_id)
            installation_id_saved = True
            logger.info(
                "Installation ID saved (installation_id='%s', env_file='%s')",
                request.installation_id,
                str(credential_manager.env_file),
            )
        else:
            logger.info("Registration completed without installation ID")

        asyncio.create_task(_schedule_shutdown(5))

        return GitHubCompleteResponse(success=True, installation_id_saved=installation_id_saved)

    @app.get(Routes.SLACK_APP)
    async def serve_slack_app():
        return FileResponse(str(Paths.SETUP_SLACK_TEMPLATE))

    @app.post(Routes.SLACK_CREATE, response_model=SlackAppCreateResponse)
    async def create_slack_app_endpoint(request: SlackAppCreateRequest):
        try:
            manifest = await slack_app_setup_service.create_manifest(request.app_name)
            response = await slack_app_setup_service.create_slack_app(manifest, request.config_token)

            if response.get("ok"):
                app_id = response["app_id"]
                return SlackAppCreateResponse(success=True, app_id=app_id, app_name=request.app_name)
            else:
                error_msg = response.get("error", "Unknown error")
                if response.get("errors"):
                    error_details = json.dumps(response["errors"], indent=2)
                    error_msg = f"{error_msg}: {error_details}"

                return SlackAppCreateResponse(success=False, error=error_msg)

        except (FileNotFoundError, ValueError, RuntimeError) as e:
            return SlackAppCreateResponse(success=False, error=str(e))
        except Exception as e:
            logger.error("Unexpected error creating Slack app: %s", e)
            return SlackAppCreateResponse(success=False, error=f"Unexpected error: {str(e)}")

    @app.post(Routes.SLACK_COMPLETE, response_model=SlackCompleteResponse)
    async def complete_slack_registration(request: SlackCompleteRequest):
        try:
            success, app_user_id, data = await slack_app_setup_service.get_app_user_id(request.bot_token)

            if not success:
                return SlackCompleteResponse(success=False, error=data.get("error", "Unknown error"))

            await credential_manager.save_slack_credentials(
                app_name=request.app_name,
                bot_token=request.bot_token,
                app_token=request.app_token,
                app_id=app_user_id,  # type: ignore
            )

            logger.info(
                "Slack credentials saved (app_name='%s', app_id='%s', user_id='%s')",
                request.app_name,
                request.app_id,
                app_user_id,
            )

            asyncio.create_task(_schedule_shutdown(5))

            return SlackCompleteResponse(success=True, app_user_id=app_user_id)

        except Exception as e:
            logger.error("Error completing Slack registration: %s", e)
            return SlackCompleteResponse(success=False)

    return app


def _render_template(template_path: Path, context: Dict[str, Any]) -> str:
    content = template_path.read_text()

    for key, value in context.items():
        escaped_value = html.escape(str(value))
        placeholder = f"{{{{ {key} }}}}"
        content = content.replace(placeholder, escaped_value)

    return content


async def _render_error_page(error_message: str, status_code: int = 500) -> HTMLResponse:
    html_content = _render_template(Paths.GITHUB_ERROR_TEMPLATE, {"error_message": error_message})
    return HTMLResponse(content=html_content, status_code=status_code)


async def _schedule_shutdown(delay_seconds: int):
    logger.info(f"Scheduling server shutdown in {delay_seconds} seconds...")
    await asyncio.sleep(delay_seconds)
    logger.info("Initiating graceful server shutdown...")
    os.kill(os.getpid(), signal.SIGTERM)
