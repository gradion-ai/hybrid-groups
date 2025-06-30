import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from hygroup.agent.default import AgentSettings, DefaultAgentRegistry, HandoffAgent
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

GRADION_AGENT_INSTRUCTIONS = """You are a helpful assistant that delegates queries to other agents if possible.
To get a list of registered agents, use the get_registered_agents tool which returns their names and description.
If the description of an agent seems appropriate for answering the query, handoff to that agent.
Otherwise, try to answer the query yourself."""


async def main(args):
    permission_store = DefaultPermissionStore() if args.user_channel else None
    request_handler: RequestHandler

    agent_registry = DefaultAgentRegistry()
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

    def create_agents():
        agent_settings = AgentSettings(
            model="openai:gpt-4.1",
            instructions=GRADION_AGENT_INSTRUCTIONS,
        )
        gradion = HandoffAgent(name="gradion", settings=agent_settings)
        gradion.tool(requires_permission=False)(agent_registry.get_registered_agents)

        return [gradion]

    manager = SessionManager(
        agent_factory=create_agents,
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
            app_id = os.environ["SLACK_APP_ID"]
            user_mapping[app_id] = "gradion"

            gateway = SlackGateway(
                session_manager=manager,
                user_mapping=user_mapping,
                app_id=app_id,
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

    await gateway.start(join=True)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", type=str, default="terminal", choices=["github", "slack", "terminal"])
    parser.add_argument("--user-channel", action="store_true", default=False)
    parser.add_argument("--user-registry", action="store_true", default=False)
    parser.add_argument("--session-id", type=str, default=None, help="session id for terminal gateway")

    asyncio.run(main(args=parser.parse_args()))
