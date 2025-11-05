import argparse
import asyncio
import importlib
import logging
from pathlib import Path

from dotenv import load_dotenv
from group_genie.agent import AgentFactory
from group_genie.logging import configure_logging
from group_genie.reasoner import GroupReasonerFactory

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


def load_factories(module_name: str, secrets_store) -> tuple[GroupReasonerFactory, AgentFactory]:
    module = importlib.import_module(module_name)

    create_group_reasoner_factory = getattr(module, "create_group_reasoner_factory")
    create_agent_factory = getattr(module, "create_agent_factory")

    group_reasoner_factory = create_group_reasoner_factory(secrets_store)
    agent_factory = create_agent_factory(secrets_store)

    return group_reasoner_factory, agent_factory


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
    group_reasoner_factory, agent_factory = load_factories(args.factory_module, secrets_store)

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
        group_reasoner_factory=group_reasoner_factory,
        agent_factory=agent_factory,
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
    parser.add_argument(
        "--factory-module",
        type=str,
        default="demo.factory.default",
        help="Module containing the agent and group reasoner factories.",
    )

    levels = {
        __name__: logging.INFO,
        "group_sense": logging.INFO,
        "group_genie": logging.DEBUG,
        "hygroup": logging.INFO,
    }

    with configure_logging(levels=levels):
        asyncio.run(main(args=parser.parse_args()))
