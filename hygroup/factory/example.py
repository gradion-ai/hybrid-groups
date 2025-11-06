import os
from pathlib import Path

from group_genie.agent import Agent, AgentFactory, AgentInfo, AsyncTool
from group_genie.agent.provider.pydantic_ai import DefaultAgent, DefaultGroupReasoner, ToolFilter
from group_genie.reasoner import GroupReasoner, GroupReasonerFactory
from group_genie.secrets import SecretsProvider
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.models.google import GoogleModelSettings

from hygroup.factory.tools.weather import get_weather_forecast


def load_system_prompt(name: str) -> str:
    path = Path(__file__).parent / "prompts" / f"{name}.md"
    return path.read_text()


def create_math_agent(secrets: dict[str, str]) -> Agent:
    ipybox_mcp_server = MCPServerStdio(
        command="uvx",
        args=["ipybox", "mcp"],
    )

    return DefaultAgent(
        system_prompt="You are a computational mathematician. For every math problem, write and execute Python code to calculate the answer.",
        model="gemini-2.5-flash",
        model_settings=GoogleModelSettings(
            google_thinking_config={
                "thinking_budget": 0,
                "include_thoughts": False,
            }
        ),
        toolsets=[ipybox_mcp_server],
    )


# --8<-- [start:office-agent]
def create_office_agent(secrets: dict[str, str]) -> Agent:
    vars = os.environ | secrets

    composio_gmail_id = vars.get("COMPOSIO_GMAIL_ID", "unknown")
    composio_gcal_id = vars.get("COMPOSIO_GOOGLECALENDAR_ID", "unknown")
    composio_user_id = vars.get("COMPOSIO_USER_ID", "")

    gmail_mcp_server = MCPServerStreamableHTTP(
        url=f"https://mcp.composio.dev/composio/server/{composio_gmail_id}?user_id={composio_user_id}",
    )

    googlecalendar_mcp_server = MCPServerStreamableHTTP(
        url=f"https://mcp.composio.dev/composio/server/{composio_gcal_id}?user_id={composio_user_id}",
    )

    claude_mcp_server = MCPServerStdio(
        command="claude",
        args=["mcp", "serve"],
    ).filtered(ToolFilter(included=["Bash"]))

    return DefaultAgent(
        system_prompt=load_system_prompt("office"),
        model="anthropic:claude-sonnet-4-5",
        toolsets=[gmail_mcp_server, googlecalendar_mcp_server, claude_mcp_server],
    )


# --8<-- [end:office-agent]


# --8<-- [start:system-agent]
def create_system_agent(
    secrets: dict[str, str],
    extra_tools: dict[str, AsyncTool],
    agent_infos: list[AgentInfo],
) -> Agent:
    from examples.prompts.system.prompt import system_prompt

    vars = os.environ | secrets

    brave_mcp_server = MCPServerStdio(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={
            "BRAVE_API_KEY": vars.get("BRAVE_API_KEY", ""),
        },
    )

    tools = [get_weather_forecast, extra_tools["run_subagent"]]
    if tool := extra_tools.get("get_group_chat_messages"):
        tools.append(tool)

    return DefaultAgent(
        system_prompt=system_prompt(agent_infos),
        model="gemini-2.5-flash",
        model_settings=GoogleModelSettings(
            google_thinking_config={
                "thinking_budget": -1,
                "include_thoughts": True,
            }
        ),
        toolsets=[brave_mcp_server],
        tools=tools,
    )


# --8<-- [end:system-agent]


def create_agent_factory(secrets_provider: SecretsProvider | None = None):
    factory = AgentFactory(
        system_agent_factory=create_system_agent,
        secrets_provider=secrets_provider,
    )

    factory.add_agent_factory_fn(
        factory_fn=create_math_agent,
        info=AgentInfo(
            name="math",
            description="Use this agent for calculations or numerical analysis. Solves math problems using Python code execution.",
        ),
    )

    factory.add_agent_factory_fn(
        factory_fn=create_office_agent,
        info=AgentInfo(
            name="office",
            description="Use this agent to manage Gmail and Google Calendar. Can fetch emails with content summaries, download PDF attachments, manage email drafts, list email labels, and find calendar events with detailed information.",
            emoji="paperclip",
        ),
    )

    return factory


def create_group_reasoner(secrets: dict[str, str], owner: str) -> GroupReasoner:
    return DefaultGroupReasoner(system_prompt=load_system_prompt("reasoner").format(owner=owner))


def create_group_reasoner_factory(secrets_provider: SecretsProvider | None = None):
    return GroupReasonerFactory(
        group_reasoner_factory_fn=create_group_reasoner,
        secrets_provider=secrets_provider,
    )
