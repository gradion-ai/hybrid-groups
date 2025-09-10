import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from hygroup.agent.registry import AgentRegistries
from hygroup.connect.composio import ComposioConnector
from hygroup.gateway import Gateway
from hygroup.gateway.github import GithubGateway
from hygroup.gateway.slack import SlackGateway, SlackHomeHandlers
from hygroup.gateway.terminal import TerminalGateway
from hygroup.session import SessionManager
from hygroup.user import RequestHandler
from hygroup.user.default import (
    DefaultPermissionStore,
    DefaultPreferenceStore,
    RequestServer,
    RichConsoleHandler,
    UserMapping,
)
from hygroup.user.default.command import DefaultCommandStore
from hygroup.user.secrets import SecretsStore


async def main(args):
    if args.user_channel == "slack" and args.gateway != "slack":
        raise ValueError("Invalid configuration: --user-channel=slack requires --gateway=slack")

    agent_registries = AgentRegistries()
    preference_store = DefaultPreferenceStore()
    permission_store = DefaultPermissionStore()
    command_store = DefaultCommandStore()
    user_mapping = UserMapping()

    secrets_store = SecretsStore(args.secrets_store)
    await secrets_store.unlock(args.secrets_store_password)

    composio_connector = ComposioConnector(secrets_store=secrets_store)
    composio_config = await composio_connector.load_config()

    request_handler: RequestHandler
    match args.user_channel:
        case "terminal":
            request_handler = RequestServer(secrets_store)
            await request_handler.start(join=False)
        case _:
            request_handler = RichConsoleHandler(
                default_permission_response=1,
                default_confirmation_response=True,
            )

    manager = SessionManager(
        agent_registries=agent_registries,
        secrets_store=secrets_store,
        permission_store=permission_store,
        preferences_store=preference_store,
        request_handler=request_handler,
        composio_config=composio_config,
        command_store=command_store,
    )

    gateway: Gateway

    match args.gateway:
        case "slack":
            mapping = await user_mapping.load("slack")
            gateway = SlackGateway(
                session_manager=manager,
                composio_connector=composio_connector,
                user_mapping=mapping,
                handle_permission_requests=args.user_channel == "slack",
                wip_update=False,
            )
            handlers = SlackHomeHandlers(
                client=gateway.client,
                app=gateway.app,
                secrets_store=secrets_store,
                preference_store=preference_store,
                user_mapping=mapping,
            )
            handlers.register()
        case "github":
            mapping = await user_mapping.load("github")
            gateway = GithubGateway(
                session_manager=manager,
                user_mapping=mapping,
            )
        case "terminal":
            gateway = TerminalGateway(
                session_manager=manager,
            )

    await gateway.start(join=True)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Hybrid Groups App Server")
    parser.add_argument(
        "--gateway",
        type=str,
        default="slack",
        choices=["github", "slack", "terminal"],
        help="The communication platform to use.",
    )
    parser.add_argument(
        "--secrets-store",
        type=Path,
        default=Path(".data", "users"),
        help="Path to the secrets store directory.",
    )
    parser.add_argument(
        "--secrets-store-password",
        type=str,
        default="admin",
        help="Admin password for creating or unlocking the secrets store.",
    )
    parser.add_argument(
        "--user-channel",
        type=str,
        default=None,
        choices=["slack", "terminal"],
        help="Channel for permission requests. If not provided, requests are auto-approved.",
    )

    args = parser.parse_args()
    asyncio.run(main(args=args))
