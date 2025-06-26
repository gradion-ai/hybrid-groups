import argparse
import asyncio
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from hygroup.agent.default import DefaultAgentRegistry
from hygroup.api.app import create_app
from hygroup.api.config import ApiServerSettings
from hygroup.gateway import Gateway
from hygroup.gateway.github import GithubGateway
from hygroup.gateway.slack import SlackGateway
from hygroup.gateway.terminal import LocalTerminalGateway, RemoteTerminalGateway
from hygroup.session import SessionManager
from hygroup.user import RequestHandler
from hygroup.user.default import (
    DefaultPermissionStore,
    DefaultUserRegistry,
    RequestServer,
    RichConsoleHandler,
)

agent_registry = DefaultAgentRegistry()


async def get_registered_agents():
    return await agent_registry.get_registered_agents()


async def main(args):
    permission_store = DefaultPermissionStore() if args.user_channel else None
    request_handler: RequestHandler

    user_registry = DefaultUserRegistry() if args.user_registry else None
    user_mapping = await user_registry.get_mapping(args.gateway) if user_registry is not None else {}

    if args.user_channel:
        request_handler = RequestServer(user_registry)
        await request_handler.start(join=False)
    else:
        request_handler = RichConsoleHandler(
            default_permission_response=1,
            default_confirmation_response=True,
        )

    manager = SessionManager(
        agent_registry=agent_registry,
        user_registry=user_registry,
        permission_store=permission_store,
        request_handler=request_handler,
    )

    gateway: Gateway
    match args.gateway:
        case "github":
            github_app_id = int(os.environ["GITHUB_APP_ID"])
            github_installation_id = int(os.environ["GITHUB_APP_INSTALLATION_ID"])
            github_private_key_path = Path(os.environ["GITHUB_APP_PRIVATE_KEY_PATH"])
            github_private_key = open(github_private_key_path, "r").read()
            github_app_username = os.environ["GITHUB_APP_USERNAME"]
            user_mapping[github_app_username] = "gradion"

            gateway = GithubGateway(
                session_manager=manager,
                user_mapping=user_mapping,
                github_app_id=github_app_id,
                github_installation_id=github_installation_id,
                github_private_key=github_private_key,
                github_app_username=github_app_username,
            )
        case "slack":
            gateway = SlackGateway(
                session_manager=manager,
                user_mapping=user_mapping,
            )
        case "terminal":
            gateway = RemoteTerminalGateway(
                session_manager=manager,
                session_id=args.session_id,
            )
        case "testing":
            gateway = LocalTerminalGateway(
                session_manager=manager,
                initial_agent_name="gradion",
                username="martin",
            )

    api_server = None
    if user_registry is not None:
        settings = ApiServerSettings()

        api_config = uvicorn.Config(
            app=create_app(
                settings,
                user_registry,
            ),
            host="0.0.0.0",
            port=settings.api_port,
            log_config=str(settings.log_config_path),
            log_level=settings.log_level.lower(),
            reload=False,
        )

        api_server = uvicorn.Server(api_config)

    if api_server is not None:
        await asyncio.gather(api_server.serve(), gateway.start(join=True))
    else:
        await gateway.start(join=True)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", type=str, default="terminal", choices=["github", "slack", "terminal"])
    parser.add_argument("--user-channel", action="store_true", default=False)
    parser.add_argument("--user-registry", action="store_true", default=False)
    parser.add_argument("--session-id", type=str, default=None, help="session id for terminal gateway")

    asyncio.run(main(args=parser.parse_args()))
