import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from hygroup.agent.default import DefaultAgentRegistry
from hygroup.gateway import Gateway
from hygroup.gateway.github import GithubGateway
from hygroup.gateway.slack import SlackGateway, SlackHomeHandlers
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
    permission_store = DefaultPermissionStore()
    user_registry = DefaultUserRegistry()
    await user_registry.unlock("admin")

    request_handler: RequestHandler
    gateway: Gateway

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

    match args.gateway:
        case "github":
            github_app_id = int(os.environ["GITHUB_APP_ID"])
            github_installation_id = int(os.environ["GITHUB_APP_INSTALLATION_ID"])
            github_private_key_path = Path(os.environ["GITHUB_APP_PRIVATE_KEY_PATH"])
            github_private_key = open(github_private_key_path, "r").read()
            github_app_username = os.environ["GITHUB_APP_USERNAME"]

            user_mappings = user_registry.get_mappings("github")
            user_mappings[github_app_username] = "gradion"

            gateway = GithubGateway(
                session_manager=manager,
                user_mapping=user_mappings,
                github_app_id=github_app_id,
                github_installation_id=github_installation_id,
                github_private_key=github_private_key,
                github_app_username=github_app_username,
            )
        case "slack":
            gateway = SlackGateway(
                session_manager=manager,
                user_mapping=user_registry.get_mappings("slack"),
                handle_permission_requests=True,
            )
            slack_home_handlers = SlackHomeHandlers(
                client=gateway._client,
                app=gateway._app,
                agent_registry=agent_registry,
            )
            slack_home_handlers.register()
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

    await gateway.start(join=True)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", type=str, default="terminal", choices=["github", "slack", "terminal"])
    parser.add_argument("--user-channel", action="store_true", default=False)
    parser.add_argument("--session-id", type=str, default=None, help="session id for terminal gateway")

    asyncio.run(main(args=parser.parse_args()))
