import argparse
import asyncio
import os
from pathlib import Path

import aiofiles
from dotenv import load_dotenv

from hygroup.agent.default import DefaultAgentRegistry
from hygroup.agent.select import AgentSelectorSettings
from hygroup.gateway import Gateway
from hygroup.gateway.github import GithubGateway
from hygroup.gateway.slack import SlackGateway, SlackHomeHandlers
from hygroup.gateway.terminal import TerminalGateway
from hygroup.session import SessionManager
from hygroup.user import RequestHandler
from hygroup.user.default import (
    DefaultPermissionStore,
    DefaultPreferenceStore,
    DefaultUserRegistry,
    RequestServer,
    RichConsoleHandler,
)

# Registry for agent configurations and factories
agent_registry = DefaultAgentRegistry()

# Database for user preferences
preference_store = DefaultPreferenceStore()


# Tool for agents to load user preferences
async def get_user_preferences(username: str):
    preferences = await preference_store.get_preferences(username)
    preferences = preferences or "n/a"
    return f"User preferences for {username}:\n{preferences}"


async def main(args):
    if args.user_channel == "slack" and args.gateway != "slack":
        raise ValueError("The 'slack' user channel is only available with the 'slack' gateway.")

    # Database for tool execution permissions (session, permanent)
    permission_store = DefaultPermissionStore()

    # A user registry that encrypts user secrets at rest with an
    # admin password.
    user_registry = DefaultUserRegistry(args.user_registry)
    await user_registry.unlock(args.user_registry_password)

    request_handler: RequestHandler
    match args.user_channel:
        case "terminal":
            # Start a server for private user channels. See
            # examples/user_channel.py for the terminal client.
            request_handler = RequestServer(user_registry)
            await request_handler.start(join=False)
        case _:
            # Log permission and confirmation requests to the console,
            # automatically approving all tool execution permissions
            # and agent selections.
            request_handler = RichConsoleHandler(
                default_permission_response=1,
                default_confirmation_response=True,
            )

    # Settings for the background reasoning agent.
    # Reasoning thoughts are logged to the console.
    selector_settings = AgentSelectorSettings()
    selector_settings.instructions_file = Path(".data", "agents", "policy.md")

    # Copy activation policy to a file, allowing edits from the
    # Slack app home view.
    if not selector_settings.instructions_file.exists():
        selector_settings.instructions_file.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(selector_settings.instructions_file, "w") as f:
            await f.write(selector_settings.instructions)

    # Manages group sessions and their persistence.
    manager = SessionManager(
        agent_registry=agent_registry,
        user_registry=user_registry,
        permission_store=permission_store,
        request_handler=request_handler,
        selector_settings=selector_settings,
    )

    # A gateway provides connectivity to platforms like Slack, GitHub, or a terminal.
    # A remote terminal interface can be used for internal experimentation and testing.
    gateway: Gateway

    match args.gateway:
        case "slack":
            gateway = SlackGateway(
                session_manager=manager,
                user_mapping=user_registry.get_mappings("slack"),
                # If True, prompt users in Slack to approve
                # tool execution via ephemeral messages.
                handle_permission_requests=args.user_channel == "slack",
            )
            handlers = SlackHomeHandlers(
                client=gateway.client,
                app=gateway.app,
                agent_registry=agent_registry,
                user_registry=user_registry,
                preference_store=preference_store,
                selector_settings=selector_settings,
            )
            handlers.register()
        case "github":
            gateway = GithubGateway(
                session_manager=manager,
                user_mapping=user_registry.get_mappings("github"),
                github_app_id=int(os.environ["GITHUB_APP_ID"]),
                github_installation_id=int(os.environ["GITHUB_APP_INSTALLATION_ID"]),
                github_private_key=Path(os.environ["GITHUB_APP_PRIVATE_KEY_PATH"]).read_text(),
                github_app_username=os.environ["GITHUB_APP_USERNAME"],
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
        "--user-registry",
        type=Path,
        default=Path(".data", "users", "registry.bin"),
        help="Path to the user registry file.",
    )
    parser.add_argument(
        "--user-registry-password",
        type=str,
        default="admin",
        help="Admin password for creating or unlocking the user registry.",
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
