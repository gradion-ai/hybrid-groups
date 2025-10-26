import os
import random
from pathlib import Path

from group_genie.agent import Agent, AgentFactory, AgentInfo, AsyncTool, GroupReasoner, GroupReasonerFactory
from group_genie.agent.provider.pydantic_ai import DefaultAgent, DefaultGroupReasoner, ToolFilter
from group_genie.secrets import SecretsProvider
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.models.google import GoogleModelSettings


def load_system_prompt(name: str) -> str:
    path = Path(__file__).parent / "prompts" / f"{name}.md"
    return path.read_text()


async def get_weather(city: str) -> str:
    """Get the weather for a city.

    Args:
        city: The city to get the weather for.

    Returns:
        The weather for the city.
    """

    conditions = ["rainy", "sunny", "cloudy"]
    condition = random.choice(conditions)
    temperature = random.randint(0, 30)
    return f"The weather in {city} is {condition} at {temperature}°C."


def create_weather_agent(secrets: dict[str, str]) -> Agent:
    return DefaultAgent(
        system_prompt="You are a weather reporting agent that reports the weather for one or more cities.",
        model="gemini-2.5-flash",
        model_settings=GoogleModelSettings(
            google_thinking_config={
                "thinking_budget": 0,
                "include_thoughts": False,
            }
        ),
        tools=[get_weather],
    )


def create_math_agent(secrets: dict[str, str]) -> Agent:
    ipybox_mcp_server = MCPServerStdio(
        command="uvx",
        args=["ipybox", "mcp"],
    )

    return DefaultAgent(
        system_prompt="You are an expert in solving mathematical problems. Always generate and execute code for solving the problems.",
        model="gemini-2.5-flash",
        model_settings=GoogleModelSettings(
            google_thinking_config={
                "thinking_budget": -1,
                "include_thoughts": True,
            }
        ),
        toolsets=[ipybox_mcp_server],
    )


def create_zotero_agent(secrets: dict[str, str]) -> Agent:
    vars = os.environ | secrets

    zotero_mcp_server = MCPServerStdio(
        command=vars["ZOTERO_MCP_EXEC"],
        args=[],
        env={
            "ZOTERO_API_KEY": vars.get("ZOTERO_API_KEY", ""),
            "ZOTERO_LIBRARY_ID": vars.get("ZOTERO_LIBRARY_ID", ""),
            "ZOTERO_LIBRARY_TYPE": vars.get("ZOTERO_LIBRARY_TYPE", ""),
        },
    ).filtered(
        ToolFilter(
            included=[
                "zotero_semantic_search",
                "zotero_search_items",
                "zotero_get_item_metadata",
                "zotero_get_collections",
                "zotero_get_collection_items",
                "zotero_get_recent",
                "zotero_update_search_database",
            ],
        ),
    )

    return DefaultAgent(
        system_prompt=load_system_prompt("zotero"),
        model="gemini-2.5-flash",
        toolsets=[zotero_mcp_server],
    )


def create_reader_agent(secrets: dict[str, str]) -> Agent:
    vars = os.environ | secrets

    reader_mcp_server = MCPServerStdio(
        command="node",
        args=[vars["READER_MCP_EXEC"]],
        env={"READWISE_TOKEN": vars.get("READWISE_TOKEN", "")},
    ).filtered(
        ToolFilter(
            excluded=[
                "readwise_list_tags",
                "readwise_update_document",
            ],
        ),
    )

    return DefaultAgent(
        system_prompt=load_system_prompt("reader"),
        model="gemini-2.5-flash",
        toolsets=[reader_mcp_server],
    )


def create_notes_agent(secrets: dict[str, str]) -> Agent:
    vars = os.environ | secrets

    notion_mcp_server = MCPServerStreamableHTTP(
        url="https://mcp.notion.com/mcp",
        headers={
            "Authorization": f"Bearer {vars.get('NOTION_ACCESS_TOKEN', '')}",
        },
    ).filtered(
        ToolFilter(
            excluded=[
                "notion-get-teams",
                "notion-get-users",
                "notion-get-user",
            ],
        ),
    )

    return DefaultAgent(
        system_prompt=load_system_prompt("notes"),
        model="anthropic:claude-sonnet-4-5",
        toolsets=[notion_mcp_server],
    )


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


def create_system_agent(
    secrets: dict[str, str],
    extra_tools: dict[str, AsyncTool],
    agent_infos: list[AgentInfo],
) -> Agent:
    from examples.prompts.system.prompt import system_prompt

    claude_code_mcp_server = MCPServerStdio(
        command="claude",
        args=["mcp", "serve"],
        env={},
    ).filtered(ToolFilter(included=["WebSearch", "WebFetch"]))

    tools = [extra_tools["run_subagent"]]
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
        toolsets=[claude_code_mcp_server],
        tools=tools,
    )


def create_agent_factory(secrets_provider: SecretsProvider | None = None):
    factory = AgentFactory(
        system_agent_factory=create_system_agent,
        secrets_provider=secrets_provider,
    )

    factory.add_agent_factory_fn(
        factory_fn=create_weather_agent,
        info=AgentInfo(
            name="weather",
            description="An agent that can report the weather for a city.",
        ),
    )

    factory.add_agent_factory_fn(
        factory_fn=create_math_agent,
        info=AgentInfo(
            name="math",
            description="An agent that can solve mathematical problems.",
        ),
    )

    factory.add_agent_factory_fn(
        factory_fn=create_zotero_agent,
        info=AgentInfo(
            name="zotero",
            description="Use this agent to search and retrieve academic papers, articles, and other scholarly materials from a Zotero library. Supports semantic search, keyword search, collection browsing, and metadata retrieval including arXiv URLs.",
        ),
    )

    factory.add_agent_factory_fn(
        factory_fn=create_reader_agent,
        info=AgentInfo(
            name="reader",
            description="Use this agent to organize and manage a Readwise Reader library. Can list documents from specific locations (new, later, archive), search for documents by keywords, save new documents from URLs, and delete documents.",
        ),
    )

    factory.add_agent_factory_fn(
        factory_fn=create_notes_agent,
        info=AgentInfo(
            name="notes",
            description="Use this agent to manage pages and databases in Notion workspaces. Can search, create, update, and organize Notion content including pages, databases, properties, and hierarchical structures.",
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
    return DefaultGroupReasoner(system_prompt=load_system_prompt("group").format(owner=owner))


def create_group_reasoner_factory(secrets_provider: SecretsProvider | None = None):
    return GroupReasonerFactory(
        group_reasoner_factory_fn=create_group_reasoner,
        secrets_provider=secrets_provider,
    )
