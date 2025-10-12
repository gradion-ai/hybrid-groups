import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from examples.registry import create_registry
from hylabs.agent import AgentRegistry
from hylabs.logging import setup_logging, shutdown_logging

from hygroup.channel import RequestServer, RichConsoleHandler
from hygroup.connect.composio import ComposioConnector
from hygroup.connect.notion import NotionAuth
from hygroup.gateway import Gateway
from hygroup.gateway.github import GithubGateway
from hygroup.gateway.slack import SlackGateway, SlackHomeHandlers
from hygroup.gateway.terminal import TerminalGateway
from hygroup.session import SessionFactory
from hygroup.user.secrets import SecretsStore
from hygroup.user.settings import SettingsStore

logger = logging.getLogger(__name__)


async def main(args):
    if args.user_channel == "slack" and args.gateway != "slack":
        raise ValueError("Invalid configuration: --user-channel=slack requires --gateway=slack")

    secrets_store = SecretsStore(root_path=args.secrets_store)
    await secrets_store.unlock(args.secrets_store_password)

    notion_auth = NotionAuth(root_path=args.secrets_store)
    await notion_auth.refresh_task(secrets_store=secrets_store)

    composio_connector = ComposioConnector(secrets_store=secrets_store)
    composio_config = await composio_connector.load_config()
    composio_config.set_env_vars()

    settings_store = SettingsStore(root_path=args.settings_store)
    agent_registry: AgentRegistry = create_registry(secrets_store)

    request_handler: RichConsoleHandler | RequestServer
    match args.user_channel:
        case "terminal":
            request_handler = RequestServer()
            await request_handler.start(join=False)
        case _:
            request_handler = RichConsoleHandler(
                default_permission_response=1,
                default_confirmation_response=True,
            )

    factory = SessionFactory(
        settings_store=settings_store,
        secrets_store=secrets_store,
        request_handler=request_handler,
        agent_registry=agent_registry,
    )

    gateway: Gateway

    match args.gateway:
        case "slack":
            gateway = SlackGateway(
                session_factory=factory,
                composio_connector=composio_connector,
                handle_permission_requests=args.user_channel == args.gateway,
            )
            handlers = SlackHomeHandlers(
                client=gateway.client,
                app=gateway.app,
                secrets_store=secrets_store,
                settings_store=settings_store,
            )
            handlers.register()
        case "github":
            gateway = GithubGateway(session_factory=factory)
        case "terminal":
            gateway = TerminalGateway(session_factory=factory)

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
        "--settings-store",
        type=Path,
        default=Path(".data", "users"),
        help="Path to the settings store directory.",
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

    listener = setup_logging(
        config={
            __name__: logging.INFO,
            "hylabs": logging.INFO,
            "hygroup": logging.INFO,
        },
    )
    asyncio.run(main(args=args))
    shutdown_logging(listener)
