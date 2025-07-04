import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from dotenv import load_dotenv
from pydantic_ai.settings import ModelSettings

from hygroup.agent.default.agent import AgentSettings
from hygroup.agent.default.registry import DefaultAgentRegistry
from tests.integration.example_tools import current_time, get_weather_forecast

# Load environment variables
load_dotenv()


def test_serialize_regular_function():
    """Test serializing a regular function returns correct module and function name."""
    serialized = AgentSettings.serialize_tool(get_weather_forecast)
    assert serialized == {"module": "tests.integration.example_tools", "function": "get_weather_forecast"}


def test_deserialize_existing_function():
    """Test deserializing an existing function works correctly."""
    tool_dict = {"module": "tests.integration.example_tools", "function": "get_weather_forecast"}
    deserialized = AgentSettings.deserialize_tool(tool_dict)
    assert deserialized is get_weather_forecast
    assert callable(deserialized)


def test_deserialize_nonexistent_module(capsys):
    """Test deserializing with non-existent module prints error and returns None."""
    tool_dict = {"module": "nonexistent.module", "function": "some_function"}
    deserialized = AgentSettings.deserialize_tool(tool_dict)

    assert deserialized is None
    captured = capsys.readouterr()
    assert "Error importing tool nonexistent.module.some_function:" in captured.out


def test_deserialize_nonexistent_function(capsys):
    """Test deserializing with non-existent function prints error and returns None."""
    tool_dict = {"module": "tests.integration.example_tools", "function": "nonexistent_function"}
    deserialized = AgentSettings.deserialize_tool(tool_dict)

    assert deserialized is None
    captured = capsys.readouterr()
    assert "Error importing tool tests.integration.example_tools.nonexistent_function:" in captured.out


def test_agent_settings_to_dict():
    """Test AgentSettings.to_dict() serializes tools correctly."""
    settings = AgentSettings(model="openai:gpt-4", instructions="Weather assistant", tools=[get_weather_forecast])

    data = settings.to_dict()

    assert data["tools"] == [{"module": "tests.integration.example_tools", "function": "get_weather_forecast"}]
    assert data["model"] == "openai:gpt-4"
    assert data["instructions"] == "Weather assistant"


def test_agent_settings_from_dict():
    """Test AgentSettings.from_dict() deserializes tools correctly."""
    data = {
        "model": "openai:gpt-4",
        "instructions": "Weather assistant",
        "tools": [
            {"module": "tests.integration.example_tools", "function": "get_weather_forecast"},
            {"module": "nonexistent.module", "function": "fake_function"},  # This should be filtered out
        ],
        "human_feedback": True,
        "model_settings": {},
        "mcp_settings": [],
    }

    settings = AgentSettings.from_dict(data)

    # Should only have the successfully imported function
    assert len(settings.tools) == 1
    assert settings.tools[0] is get_weather_forecast
    assert settings.model == "openai:gpt-4"
    assert settings.instructions == "Weather assistant"


def test_round_trip_serialization():
    """Test that serializing and deserializing preserves the function."""
    original_settings = AgentSettings(model="openai:gpt-4", instructions="Test agent", tools=[get_weather_forecast])

    # Serialize to dict
    data = original_settings.to_dict()

    # Deserialize from dict
    restored_settings = AgentSettings.from_dict(data)

    # Check that the tool was preserved
    assert len(restored_settings.tools) == 1
    assert restored_settings.tools[0] is get_weather_forecast


@pytest.mark.asyncio
async def test_registry_stores_and_retrieves_tools():
    """Test that registry properly stores and retrieves agents with tools."""
    api_key = os.getenv("OPENAI_API_KEY")
    model_settings: ModelSettings = ModelSettings(api_key=api_key) if api_key else ModelSettings()

    with TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "test_registry.json"
        registry = DefaultAgentRegistry(registry_path)

        # Create agent settings with tools
        settings = AgentSettings(
            model="gpt-3.5-turbo",
            instructions="Weather assistant that can get weather forecasts",
            tools=[get_weather_forecast],
            model_settings=model_settings,
        )

        # Add to registry
        await registry.add_config("weather", "Weather forecast agent", settings)

        # Create agent from registry
        agent = await registry.create_agent("weather")

        # Verify the agent has the tools
        assert hasattr(agent, "settings")
        assert len(agent.settings.tools) == 1
        assert agent.settings.tools[0] is get_weather_forecast


@pytest.mark.asyncio
async def test_registry_handles_missing_tools_gracefully(capsys):
    """Test that registry handles missing tools gracefully when loading."""
    api_key = os.getenv("OPENAI_API_KEY")
    model_settings: ModelSettings = ModelSettings(api_key=api_key) if api_key else ModelSettings()

    with TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "test_registry.json"
        registry = DefaultAgentRegistry(registry_path)

        # Manually create a registry entry with a non-existent tool
        registry._tinydb.insert(
            {
                "name": "test_agent",
                "description": "Test agent with missing tool",
                "handoff": False,
                "settings": {
                    "model": "gpt-3.5-turbo",
                    "instructions": "Test instructions",
                    "human_feedback": True,
                    "model_settings": model_settings,
                    "mcp_settings": [],
                    "tools": [{"module": "nonexistent.module", "function": "missing_function"}],
                },
            }
        )

        # Create agent from registry
        agent = await registry.create_agent("test_agent")

        # Should create agent successfully but without the missing tool
        assert hasattr(agent, "settings")
        assert len(agent.settings.tools) == 0

        # Check that error was printed
        captured = capsys.readouterr()
        assert "Error importing tool nonexistent.module.missing_function:" in captured.out


@pytest.mark.asyncio
async def test_full_workflow_with_multiple_tools():
    """Test full workflow with agent containing multiple tools."""
    api_key = os.getenv("OPENAI_API_KEY")
    model_settings: dict[str, Any] = {"api_key": api_key} if api_key else {}

    with TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "test_registry.json"
        registry = DefaultAgentRegistry(registry_path)

        # Create agent settings with multiple tools
        settings = AgentSettings(
            model="gpt-3.5-turbo",
            instructions="Multi-tool assistant",
            tools=[get_weather_forecast, current_time],
            model_settings=model_settings,
        )

        # Add to registry
        await registry.add_config("multi_tool", "Agent with multiple tools", settings)

        # Retrieve config
        config = await registry.get_config("multi_tool")
        assert config is not None
        assert len(config["settings"]["tools"]) == 2
        assert {
            "module": "tests.integration.example_tools",
            "function": "get_weather_forecast",
        } in config["settings"]["tools"]
        assert {"module": "tests.integration.example_tools", "function": "current_time"} in config["settings"]["tools"]

        # Create agent from registry
        agent = await registry.create_agent("multi_tool")

        # Verify both tools are present
        assert len(agent.settings.tools) == 2
        tool_names = {tool.__name__ for tool in agent.settings.tools}
        assert "get_weather_forecast" in tool_names
        assert "current_time" in tool_names
