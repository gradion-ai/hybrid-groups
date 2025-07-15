import asyncio
import os
import textwrap

from demo.weather import get_weather_forecast
from hygroup.agent.default import AgentSettings, MCPSettings
from hygroup.scripts.server import agent_registry, get_user_preferences

INSTRUCTION_TEMPLATE = """{role_description}

You are a diligent agent. You must continue working until the user's query is completely resolved before ending your turn. Only terminate if the task is done or if you need more information from the user. If you are unsure about any part of the user's request, use your tools to find the information; do not guess or invent answers.

Your instructions are:
1. Your input is a query in the format <query sender="sender_name" ...>. You MUST identify the sender_name.
2. Before proceeding, use the `get_user_preferences` tool with the sender_name as the argument to obtain the sender's preferences. This is a mandatory first step.
3. Plan your actions before using tools and reflect on the outcomes of tool calls to decide the next action.
4. Follow the agent-specific steps below to perform your main task.

{agent_specific_steps}

5. Formulate your final response according to the user preferences obtained in step 2.
"""


def apply_template(role_description: str, agent_specific_steps: str) -> str:
    return INSTRUCTION_TEMPLATE.format(
        role_description=role_description,
        agent_specific_steps=textwrap.indent(agent_specific_steps, "  "),
    )


SCRAPE_AGENT_ROLE = "You are an agent that accurately scrapes the content of individual web pages."
SCRAPE_AGENT_STEPS = """- Use the `firecrawl_scrape` tool to scrape the web page requested by the user."""
SCRAPE_AGENT_INSTRUCTIONS = apply_template(SCRAPE_AGENT_ROLE, SCRAPE_AGENT_STEPS)


SEARCH_AGENT_ROLE = "You are an agent that searches the web to find up-to-date information."
SEARCH_AGENT_STEPS = """- Use the `brave_web_search` tool to perform a web search based on the user's query."""
SEARCH_AGENT_INSTRUCTIONS = apply_template(SEARCH_AGENT_ROLE, SEARCH_AGENT_STEPS)


ZOTERO_AGENT_ROLE = "You are an expert at reading from and updating a Zotero library."
ZOTERO_AGENT_STEPS = """- To handle the user's request, use the Zotero-related tools you have available.
- For searching items, you MUST always use the `zotero_semantic_search` tool.
- For each item found in the search results, you MUST make a parallel call to the `zotero_get_item_metadata` tool to retrieve its title and a valid link.
- You MUST include the retrieved links in your final response. Never invent links."""
ZOTERO_AGENT_INSTRUCTIONS = apply_template(ZOTERO_AGENT_ROLE, ZOTERO_AGENT_STEPS)


READER_AGENT_ROLE = "You are an expert at managing a Readwise Reader library, including reading lists and items."
READER_AGENT_STEPS = """- Use the `readwise` tools you have available to read from or update the user's items."""
READER_AGENT_INSTRUCTIONS = apply_template(READER_AGENT_ROLE, READER_AGENT_STEPS)


WEATHER_AGENT_ROLE = "You are an agent that provides weather forecasts for any location and date."
WEATHER_AGENT_STEPS = """- Use the `get_weather_forecast` tool to get the weather forecast.
- You MUST use this tool for any date the user provides, provided it is **today or any date in the future**, including dates far in the future."""
WEATHER_AGENT_INSTRUCTIONS = apply_template(WEATHER_AGENT_ROLE, WEATHER_AGENT_STEPS)


# This prompt is from the tiny-agents dataset at https://huggingface.co/datasets/tiny-agents/tiny-agents
BROWSER_AGENT_INSTRUCTIONS = """You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved, or if you need more info from the user to solve the problem.
If you are not sure about anything pertaining to the user's request, use your tools to read files and gather the relevant information: do NOT guess or make up an answer.
You MUST plan extensively before each function call, and reflect extensively on the outcomes of the previous function calls. DO NOT do this entire process by making function calls only, as this can impair your ability to solve the problem and think insightfully.
"""


GENERAL_AGENT_INSTRUCTIONS = """You can answer questions about available agents in the system using the get_registered_agents tool.
If you receive a query that one of the registered agents can handle delegate to that agent. Otherwise try to answer the query yourself.
Never delegate to yourself, the "general" agent.
"""


def scrape_agent_config():
    firecrawl_settings = MCPSettings(
        server_config={
            "command": "npx",
            "args": ["-y", "firecrawl-mcp"],
            "env": {
                "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}",
                "FIRECRAWL_RETRY_MAX_ATTEMPTS": "2",
            },
        },
        session_scope=False,
    )

    agent_settings = AgentSettings(
        model="gemini-2.5-flash",
        instructions=SCRAPE_AGENT_INSTRUCTIONS,
        mcp_settings=[firecrawl_settings],
        tools=[get_user_preferences],
    )

    return {
        "name": "scrape",
        "description": "An agent that can scrape individual web pages.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "page_facing_up",
    }


def search_agent_config():
    brave_search_settings = MCPSettings(
        server_config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {
                "BRAVE_API_KEY": "${BRAVE_API_KEY}",
            },
        },
        session_scope=False,
    )

    agent_settings = AgentSettings(
        model="gemini-2.5-flash",
        instructions=SEARCH_AGENT_INSTRUCTIONS,
        mcp_settings=[brave_search_settings],
        tools=[get_user_preferences],
    )

    return {
        "name": "search",
        "description": "An agent that can search the web.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "mag",
    }


def zotero_agent_config(zotero_mcp_exec: str):
    zotero_settings = MCPSettings(
        server_config={
            "command": zotero_mcp_exec,
            "args": [],
            "env": {
                "ZOTERO_API_KEY": "${ZOTERO_API_KEY}",
                "ZOTERO_LIBRARY_ID": "${ZOTERO_LIBRARY_ID}",
                "ZOTERO_LIBRARY_TYPE": "${ZOTERO_LIBRARY_TYPE}",
            },
        },
        session_scope=False,
    )

    fetch_settings = MCPSettings(
        server_config={
            "command": "uvx",
            "args": ["mcp-server-fetch"],
        },
        session_scope=True,
    )
    agent_settings = AgentSettings(
        model="gemini-2.5-flash",
        instructions=ZOTERO_AGENT_INSTRUCTIONS,
        mcp_settings=[zotero_settings, fetch_settings],
        tools=[get_user_preferences],
    )

    return {
        "name": "zotero",
        "description": "An agent that can read and update a Zotero library.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "books",
    }


def reader_agent_config(reader_mcp_exec: str):
    reader_settings = MCPSettings(
        server_config={
            "command": "node",
            "args": [reader_mcp_exec],
            "env": {"READWISE_TOKEN": "${READWISE_TOKEN}"},
        },
        session_scope=False,
    )

    agent_settings = AgentSettings(
        model="gemini-2.5-pro",
        instructions=READER_AGENT_INSTRUCTIONS,
        mcp_settings=[reader_settings],
        tools=[get_user_preferences],
    )

    return {
        "name": "reader",
        "description": "An agent that can read and update items in Readwise Reader.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "clock10",
    }


def weather_agent_config():
    agent_settings = AgentSettings(
        model="gemini-2.5-flash",
        instructions=WEATHER_AGENT_INSTRUCTIONS,
        mcp_settings=[],
        tools=[get_weather_forecast, get_user_preferences],
    )

    return {
        "name": "weather",
        "description": "An agent that retrieve weather information for today or specific dates in the future.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "mostly_sunny",
    }


def browser_agent_config():
    playwright_server_settings = MCPSettings(
        server_config={
            "command": "npx",
            "args": ["@playwright/mcp@latest"],
        },
        session_scope=True,
    )

    agent_settings = AgentSettings(
        model="gemini-2.5-flash",
        instructions=BROWSER_AGENT_INSTRUCTIONS,
        mcp_settings=[playwright_server_settings],
    )

    return {
        "name": "browser",
        "description": "An agent that can use an internet browser.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "earth_americas",
    }


def general_agent_config():
    agent_settings = AgentSettings(
        model="gemini-2.5-flash",
        instructions=GENERAL_AGENT_INSTRUCTIONS,
        mcp_settings=[],
        tools=[get_registered_agents],
    )

    return {
        "name": "general",
        "description": "An agent that can answer questions about available agents in the system and delegate to them if appropriate. Can answer general questions if no other agent is appropriate.",
        "settings": agent_settings,
        "handoff": True,
        "emoji": "brain",
    }


async def get_registered_agents():
    return await agent_registry.get_registered_agents()


async def main():
    await agent_registry.remove_configs()

    await agent_registry.add_config(**weather_agent_config())
    await agent_registry.add_config(**general_agent_config())

    if os.environ.get("FIRECRAWL_API_KEY"):
        # see https://docs.firecrawl.com/docs/api-reference/api-reference
        await agent_registry.add_config(**scrape_agent_config())
    if os.environ.get("BRAVE_API_KEY"):
        # see https://api-dashboard.search.brave.com/app/keys
        await agent_registry.add_config(**search_agent_config())
    if mcp_exec := os.environ.get("ZOTERO_MCP_EXEC"):
        # see https://github.com/54yyyu/zotero-mcp
        await agent_registry.add_config(**zotero_agent_config(mcp_exec))
    if mcp_exec := os.environ.get("READER_MCP_EXEC"):
        # see https://github.com/edricgsh/Readwise-Reader-MCP
        await agent_registry.add_config(**reader_agent_config(mcp_exec))


if __name__ == "__main__":
    asyncio.run(main())
