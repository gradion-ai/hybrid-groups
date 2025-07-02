import asyncio

from examples.app_server import agent_registry, get_registered_agents
from examples.weather import get_weather_forecast
from hygroup.agent.default import AgentSettings, MCPSettings

BROWSER_AGENT_INSTRUCTIONS = """You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved, or if you need more info from the user to solve the problem.
If you are not sure about anything pertaining to the user's request, use your tools to read files and gather the relevant information: do NOT guess or make up an answer.
You MUST plan extensively before each function call, and reflect extensively on the outcomes of the previous function calls. DO NOT do this entire process by making function calls only, as this can impair your ability to solve the problem and think insightfully."""

SEARCH_AGENT_INSTRUCTIONS = """You can search the web using the brave_web_search tool.
For all other questions say 'I don't know'.
Be concise."""

SCRAPE_AGENT_INSTRUCTIONS = """You can scrape individual web pages using the scrape tool from the firecrawl_scrape tool.
For all other questions say 'I don't know'.
Be concise."""

WEATHER_AGENT_INSTRUCTIONS = """You can get weather forecasts for today or dates in the future.
Always use the get_weather_forecast tool for any date provided, even if it is far in the future.
For all other questions say 'I don't know'.
Be concise."""

GENERAL_AGENT_INSTRUCTIONS = """You can answer questions about available agents in the system using the get_registered_agents tool.
If you receive a question that one of the registered agents can answer delegate to that agent. Otherwise say try to answer the question yourself.
Never delegate to yourself, the "gradion" agent.
"""


def browser_agent_config():
    playwright_server_settings = MCPSettings(
        server_config={
            "command": "npx",
            "args": ["@playwright/mcp@latest"],
        },
        session_scope=True,
    )

    agent_settings = AgentSettings(
        model="openai:gpt-4.1",
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
        model="openai:gpt-4.1",
        instructions=SEARCH_AGENT_INSTRUCTIONS,
        mcp_settings=[brave_search_settings],
    )

    return {
        "name": "search",
        "description": "An agent that can search the web.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "mag",
    }


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
        model="openai:gpt-4.1",
        instructions=SCRAPE_AGENT_INSTRUCTIONS,
        mcp_settings=[firecrawl_settings],
    )

    return {
        "name": "scrape",
        "description": "An agent that can scrape individual web pages.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "page_facing_up",
    }


def weather_agent_config():
    agent_settings = AgentSettings(
        model="openai:gpt-4.1",
        instructions=WEATHER_AGENT_INSTRUCTIONS,
        mcp_settings=[],
        tools=[get_weather_forecast],
    )

    return {
        "name": "weather",
        "description": "An agent that retrieve weather information for today or specific dates in the future.",
        "settings": agent_settings,
        "handoff": False,
        "emoji": "mostly_sunny",
    }


def general_agent_config():
    agent_settings = AgentSettings(
        model="openai:gpt-4.1",
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


async def main():
    await agent_registry.remove_configs()
    await agent_registry.add_config(**browser_agent_config())
    await agent_registry.add_config(**search_agent_config())
    await agent_registry.add_config(**scrape_agent_config())
    await agent_registry.add_config(**weather_agent_config())
    await agent_registry.add_config(**general_agent_config())


if __name__ == "__main__":
    asyncio.run(main())
