import asyncio

from pydantic_ai.models.google import GoogleModelSettings

from hygroup.agent.default import AgentSettings, MCPSettings
from hygroup.agent.registry import AgentRegistry
from hygroup.agent.system import system_agent_instructions
from hygroup.examples.template import InstructionsTemplate
from hygroup.examples.weather import get_weather_forecast

OFFICE_AGENT_ROLE = "You are an office assistant that manages Gmail, Google Calendar, and Google Drive to help users with email drafting, scheduling tasks, and document management."
OFFICE_AGENT_STEPS = """- Use the Gmail tools to read, search, and manage emails as requested by the user.
- You can create email drafts but CANNOT send emails directly - inform users that drafts will be created for their review.
- Use the Google Calendar tools to view, create, update, and manage calendar events.
- Use the Google Drive tools to list, search, create, read, update, and manage documents, spreadsheets, presentations, and other files.
- When scheduling meetings, check calendar availability first before creating events.
- For email tasks, search for existing conversations before creating draft replies when appropriate.
- For document tasks, search for existing files before creating new ones when appropriate.
- Always confirm important actions (like creating drafts, scheduling meetings, or modifying documents) by summarizing what you're about to do."""


MATH_AGENT_ROLE = "You are a computational assistant that can execute Python code to perform calculations, analyze data, and generate visualizations."
MATH_AGENT_STEPS = """- Use the `ipybox_exec_cell` tool to:
  - Perform numerical calculations and mathematical operations
  - Analyze data and run statistical computations
  - Generate plots and visualizations using matplotlib, seaborn, or other libraries
  - Execute arbitrary Python code in a secure sandbox environment
- Show your work by displaying the output of the code you execute
- Explain results clearly when needed"""


# --8<-- [start:office-agent]
def office_agent_config(template: InstructionsTemplate):
    gmail_settings = MCPSettings(
        server_config={
            "url": "https://mcp.composio.dev/composio/server/${COMPOSIO_GMAIL_ID}?user_id=${COMPOSIO_USER_ID}",
        },
    )

    googlecalendar_settings = MCPSettings(
        server_config={
            "url": "https://mcp.composio.dev/composio/server/${COMPOSIO_GOOGLECALENDAR_ID}?user_id=${COMPOSIO_USER_ID}",
        },
    )

    googledrive_settings = MCPSettings(
        server_config={
            "url": "https://mcp.composio.dev/composio/server/${COMPOSIO_GOOGLEDRIVE_ID}?user_id=${COMPOSIO_USER_ID}",
        },
    )

    agent_settings = AgentSettings(
        model="openai:gpt-5-mini",
        instructions=template.apply(OFFICE_AGENT_ROLE, OFFICE_AGENT_STEPS),
        mcp_settings=[
            gmail_settings,
            googlecalendar_settings,
            googledrive_settings,
        ],
    )

    return {
        "name": "office",
        "description": "An agent that can manage the user's Gmail, Google Calendar, and Google Drive.",
        "settings": agent_settings,
        "emoji": "paperclip",
    }


# --8<-- [end:office-agent]


def math_agent_config(template: InstructionsTemplate):
    ipybox_settings = MCPSettings(
        server_config={
            "command": "uvx",
            "args": ["ipybox", "mcp"],
        },
    )

    agent_settings = AgentSettings(
        model="gemini-2.5-pro",
        instructions=template.apply(MATH_AGENT_ROLE, MATH_AGENT_STEPS),
        model_settings=GoogleModelSettings(
            google_thinking_config={
                "include_thoughts": True,
            }
        ),
        mcp_settings=[ipybox_settings],
    )

    return {
        "name": "math",
        "description": "An agent that executes Python code for calculations, data analysis, and visualizations.",
        "settings": agent_settings,
        "emoji": "1234",
    }


# --8<-- [start:system-agent]
def system_agent_config():
    brave_search_settings = MCPSettings(
        server_config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {
                "BRAVE_API_KEY": "${BRAVE_API_KEY}",
            },
        },
    )

    system_agent_settings = AgentSettings(
        instructions=system_agent_instructions(),
        model="gemini-2.5-flash",
        model_settings=GoogleModelSettings(
            google_thinking_config={
                "include_thoughts": True,
            }
        ),
        mcp_settings=[brave_search_settings],
        tools=[get_weather_forecast],
    )

    return {
        "name": "system",
        "description": "The system agent.",
        "settings": system_agent_settings,
    }


# --8<-- [end:system-agent]


async def main():
    template = await InstructionsTemplate.load()

    agent_registry = AgentRegistry()
    agent_registry.remove_configs()

    agent_registry.add_config(**system_agent_config())
    agent_registry.add_config(**office_agent_config(template))
    agent_registry.add_config(**math_agent_config(template))

    await agent_registry.save()


if __name__ == "__main__":
    asyncio.run(main())
