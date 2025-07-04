"""Test suite for AgentFactory implementation."""

import os
from pathlib import Path
from typing import Any, Iterator

import pytest
from dotenv import load_dotenv
from pydantic_ai.settings import ModelSettings

from hygroup.agent.default import AgentSettings, DefaultAgent, DefaultAgentRegistry, HandoffAgent, MCPSettings

# Load environment variables
load_dotenv()


@pytest.fixture
def test_agents_dir(tmp_path) -> Iterator[Path]:
    """Provide a temporary directory for agent storage."""
    yield tmp_path / "test_agents"
    # Cleanup is handled automatically by tmp_path


@pytest.fixture
def registry(test_agents_dir) -> DefaultAgentRegistry:
    """Provide an AgentRegistry instance for testing."""
    registry_path = Path(test_agents_dir) / "registry.json"
    return DefaultAgentRegistry(registry_path)


@pytest.fixture
def api_key() -> str | None:
    """Provide API key for testing."""
    return os.getenv("OPENAI_API_KEY")


@pytest.fixture
def model_settings(api_key) -> ModelSettings:
    """Provide model settings with API key if available."""
    return ModelSettings(api_key=api_key) if api_key else ModelSettings()


@pytest.fixture
def default_settings(model_settings, mcp_stdio_settings) -> AgentSettings:
    """Provide default AgentSettings for testing."""
    return AgentSettings(
        model="gpt-3.5-turbo",
        instructions="You are a helpful assistant.",
        human_feedback=True,
        model_settings=model_settings,
        mcp_settings=[mcp_stdio_settings],
    )


@pytest.fixture
def handoff_settings(model_settings, mcp_http_settings) -> AgentSettings:
    """Provide handoff AgentSettings for testing."""
    return AgentSettings(
        model="gpt-4",
        instructions="You can handoff to other agents.",
        human_feedback=False,
        model_settings=model_settings,
        mcp_settings=[mcp_http_settings],
    )


@pytest.fixture
def mcp_stdio_settings() -> MCPSettings:
    """Provide MCP server settings for stdio testing."""
    return MCPSettings(server_config={"command": "foo", "args": ["bar"]}, session_scope=True)


@pytest.fixture
def mcp_http_settings() -> MCPSettings:
    """Provide MCP server settings for HTTP testing."""
    return MCPSettings(server_config={"url": "http://localhost:8000/mcp"}, session_scope=False)


@pytest.mark.asyncio
async def test_factory_initialization(registry: DefaultAgentRegistry, test_agents_dir: Path):
    """Test that factory initializes correctly."""
    expected_registry_path = test_agents_dir / "registry.json"
    assert registry.registry_path == expected_registry_path
    assert registry.registry_path.parent.exists()
    assert hasattr(registry, "_tinydb")


@pytest.mark.asyncio
async def test_empty_descriptions_initially(registry: DefaultAgentRegistry):
    """Test that descriptions returns empty dict initially."""
    descriptions = await registry.get_descriptions()
    assert descriptions == {}


@pytest.mark.asyncio
async def test_register_default_agent(registry: DefaultAgentRegistry, default_settings: AgentSettings):
    """Test registering a default agent."""
    await registry.add_config(name="test-agent", description="A test agent", settings=default_settings, handoff=False)

    descriptions = await registry.get_descriptions()
    assert descriptions == {"test-agent": "A test agent"}


@pytest.mark.asyncio
async def test_register_handoff_agent(registry: DefaultAgentRegistry, handoff_settings: AgentSettings):
    """Test registering a handoff agent."""
    await registry.add_config(
        name="handoff-agent", description="A handoff agent", settings=handoff_settings, handoff=True
    )

    descriptions = await registry.get_descriptions()
    assert descriptions == {"handoff-agent": "A handoff agent"}


@pytest.mark.asyncio
async def test_create_default_agent(registry: DefaultAgentRegistry, default_settings: AgentSettings):
    """Test creating a default agent."""
    await registry.add_config(name="test-agent", description="A test agent", settings=default_settings, handoff=False)

    agent = await registry.create_agent("test-agent")
    assert isinstance(agent, DefaultAgent)
    assert agent.name == "test-agent"
    assert agent.settings.model == "gpt-3.5-turbo"
    assert agent.settings.instructions == "You are a helpful assistant."
    assert agent.settings.human_feedback is True


@pytest.mark.asyncio
async def test_create_handoff_agent(registry: DefaultAgentRegistry, handoff_settings: AgentSettings):
    """Test creating a handoff agent."""
    await registry.add_config(
        name="handoff-agent", description="A handoff agent", settings=handoff_settings, handoff=True
    )

    agent = await registry.create_agent("handoff-agent")
    assert isinstance(agent, HandoffAgent)
    assert agent.name == "handoff-agent"
    assert agent.settings.model == "gpt-4"
    assert agent.settings.instructions == "You can handoff to other agents."
    assert agent.settings.human_feedback is False


@pytest.mark.asyncio
async def test_multiple_agents(
    registry: DefaultAgentRegistry, default_settings: AgentSettings, handoff_settings: AgentSettings
):
    """Test registering and managing multiple agents."""
    await registry.add_config(name="agent1", description="First agent", settings=default_settings, handoff=False)
    await registry.add_config(name="agent2", description="Second agent", settings=handoff_settings, handoff=True)

    descriptions = await registry.get_descriptions()
    expected = {"agent1": "First agent", "agent2": "Second agent"}
    assert descriptions == expected


@pytest.mark.asyncio
async def test_deregister_agent(
    registry: DefaultAgentRegistry, default_settings: AgentSettings, handoff_settings: AgentSettings
):
    """Test deregistering an agent."""
    await registry.add_config(name="agent1", description="First agent", settings=default_settings, handoff=False)
    await registry.add_config(name="agent2", description="Second agent", settings=handoff_settings, handoff=True)
    await registry.remove_config("agent1")

    descriptions = await registry.get_descriptions()
    assert descriptions == {"agent2": "Second agent"}


@pytest.mark.asyncio
async def test_duplicate_name_error(registry: DefaultAgentRegistry, default_settings: AgentSettings):
    """Test that registering duplicate names raises ValueError."""
    await registry.add_config(name="test-agent", description="First agent", settings=default_settings, handoff=False)

    with pytest.raises(ValueError, match="Agent with name 'test-agent' already exists"):
        await registry.add_config(
            name="test-agent", description="Duplicate agent", settings=default_settings, handoff=False
        )


@pytest.mark.asyncio
async def test_create_nonexistent_agent_error(registry: DefaultAgentRegistry):
    """Test that creating non-existent agent raises ValueError."""
    with pytest.raises(ValueError, match="No agent registered with name 'nonexistent'"):
        await registry.create_agent("nonexistent")


@pytest.mark.asyncio
async def test_deregister_nonexistent_agent_error(registry: DefaultAgentRegistry):
    """Test that deregistering non-existent agent raises ValueError."""
    with pytest.raises(ValueError, match="No agent registered with name 'nonexistent'"):
        await registry.remove_config("nonexistent")


@pytest.mark.asyncio
async def test_agent_settings_roundtrip(registry: DefaultAgentRegistry, api_key: str):
    """Test that AgentSettings survive roundtrip through storage."""
    model_settings: dict[str, Any] = {"temperature": 0.7, "max_tokens": 1000}
    if api_key:
        model_settings["api_key"] = api_key

    mcp_settings = MCPSettings(server_config={"command": "test", "args": ["--debug"]}, session_scope=True)

    original_settings = AgentSettings(
        model="gpt-4",
        instructions="Complex instructions with special chars: !@#$%",
        human_feedback=False,
        model_settings=model_settings,
        mcp_settings=[mcp_settings],
    )

    await registry.add_config(
        name="roundtrip-agent", description="Agent for roundtrip test", settings=original_settings, handoff=False
    )

    agent = await registry.create_agent("roundtrip-agent")
    restored_settings = agent.settings

    assert restored_settings.model == original_settings.model
    assert restored_settings.instructions == original_settings.instructions
    assert restored_settings.human_feedback == original_settings.human_feedback
    assert restored_settings.model_settings == original_settings.model_settings
    assert restored_settings.mcp_settings == original_settings.mcp_settings


@pytest.mark.asyncio
async def test_model_as_dict_basic(registry: DefaultAgentRegistry, mcp_stdio_settings: MCPSettings):
    """Test registering and creating an agent with model as a dictionary."""
    model_dict = {
        "class": "pydantic_ai.models.openai.OpenAIModel",
        "args": {
            "model_name": "gpt-3.5-turbo",
        },
    }

    settings = AgentSettings(
        model=model_dict,
        instructions="Test agent with dict model",
        human_feedback=True,
        mcp_settings=[mcp_stdio_settings],
    )

    await registry.add_config(
        name="dict-model-agent", description="Agent with dictionary model config", settings=settings, handoff=False
    )

    descriptions = await registry.get_descriptions()
    assert "dict-model-agent" in descriptions

    agent = await registry.create_agent("dict-model-agent")
    assert isinstance(agent, DefaultAgent)
    assert agent.name == "dict-model-agent"
    assert agent.settings.instructions == "Test agent with dict model"


@pytest.mark.asyncio
async def test_model_as_dict_with_provider(registry: DefaultAgentRegistry, mcp_http_settings: MCPSettings):
    """Test agent with model dict containing custom provider configuration."""
    model_dict = {
        "class": "pydantic_ai.models.openai.OpenAIModel",
        "args": {
            "model_name": "llama3.1:8b-instruct-fp16",
            "provider": {
                "class": "pydantic_ai.providers.openai.OpenAIProvider",
                "args": {
                    "base_url": "http://localhost:11434/v1",
                },
            },
        },
    }

    settings = AgentSettings(
        model=model_dict,
        instructions="Local LLM agent",
        human_feedback=False,
        mcp_settings=[mcp_http_settings],
    )

    await registry.add_config(
        name="local-llm-agent",
        description="Agent using local LLM with custom provider",
        settings=settings,
        handoff=True,
    )

    agent = await registry.create_agent("local-llm-agent")
    assert isinstance(agent, HandoffAgent)
    assert agent.settings.human_feedback is False


@pytest.mark.asyncio
async def test_model_dict_persistence(registry: DefaultAgentRegistry, test_agents_dir: Path):
    """Test that model dict configuration persists correctly across registry instances."""
    registry_path = Path(test_agents_dir) / "registry.json"

    model_dict = {
        "class": "pydantic_ai.models.openai.OpenAIModel",
        "args": {
            "model_name": "gpt-4",
            "provider": {
                "class": "pydantic_ai.providers.openai.OpenAIProvider",
                "args": {"base_url": "https://api.custom-openai.com/v1", "api_key": "test-key-123"},
            },
        },
    }

    settings = AgentSettings(
        model=model_dict,
        instructions="Persistent dict model agent",
        human_feedback=True,
        model_settings={"temperature": 0.5},
    )

    # Create agent with first registry instance
    registry1 = DefaultAgentRegistry(registry_path)
    await registry1.add_config(
        name="persist-dict-agent", description="Test persistence of dict models", settings=settings, handoff=False
    )

    # Load with second registry instance
    registry2 = DefaultAgentRegistry(registry_path)
    agent = await registry2.create_agent("persist-dict-agent")

    # Verify model dict was preserved
    assert isinstance(agent.settings.model, dict)
    assert agent.settings.model["class"] == "pydantic_ai.models.openai.OpenAIModel"
    assert agent.settings.model["args"]["model_name"] == "gpt-4"
    assert agent.settings.model["args"]["provider"]["class"] == "pydantic_ai.providers.openai.OpenAIProvider"
    assert agent.settings.model["args"]["provider"]["args"]["base_url"] == "https://api.custom-openai.com/v1"


@pytest.mark.asyncio
async def test_mixed_model_types(registry: DefaultAgentRegistry):
    """Test registry can handle both string and dict model configurations simultaneously."""
    # Agent with string model
    string_settings = AgentSettings(
        model="gpt-3.5-turbo",
        instructions="String model agent",
        human_feedback=True,
    )

    # Agent with dict model
    dict_settings = AgentSettings(
        model={"class": "pydantic_ai.models.openai.OpenAIModel", "args": {"model_name": "gpt-4"}},
        instructions="Dict model agent",
        human_feedback=False,
    )

    await registry.add_config(
        name="string-agent", description="Agent with string model", settings=string_settings, handoff=False
    )

    await registry.add_config(
        name="dict-agent", description="Agent with dict model", settings=dict_settings, handoff=True
    )

    # Verify both agents exist
    descriptions = await registry.get_descriptions()
    assert len(descriptions) == 2
    assert "string-agent" in descriptions
    assert "dict-agent" in descriptions

    # Create and verify string model agent
    string_agent = await registry.create_agent("string-agent")
    assert isinstance(string_agent, DefaultAgent)
    assert isinstance(string_agent.settings.model, str)
    assert string_agent.settings.model == "gpt-3.5-turbo"

    # Create and verify dict model agent
    dict_agent = await registry.create_agent("dict-agent")
    assert isinstance(dict_agent, HandoffAgent)
    assert isinstance(dict_agent.settings.model, dict)


@pytest.mark.asyncio
async def test_complex_model_dict_with_all_settings(registry: DefaultAgentRegistry, api_key: str | None):
    """Test agent with complex model dict including all possible settings."""
    model_dict = {
        "class": "pydantic_ai.models.openai.OpenAIModel",
        "args": {
            "model_name": "gpt-4-turbo",
            "provider": {
                "class": "pydantic_ai.providers.openai.OpenAIProvider",
                "args": {
                    "base_url": "https://api.openai.com/v1",
                    "api_key": api_key or "test-api-key",
                },
            },
        },
    }

    mcp_settings = [
        MCPSettings(server_config={"command": "test-mcp", "args": ["--verbose"]}, session_scope=True),
        MCPSettings(server_config={"url": "http://mcp.example.com"}, session_scope=False),
    ]

    settings = AgentSettings(
        model=model_dict,
        instructions="Complex agent with all settings",
        human_feedback=True,
        model_settings={
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.9,
            "frequency_penalty": 0.5,
            "presence_penalty": 0.5,
        },
        mcp_settings=mcp_settings,
    )

    await registry.add_config(
        name="complex-dict-agent",
        description="Agent with complex dictionary model configuration",
        settings=settings,
        handoff=True,
    )

    agent = await registry.create_agent("complex-dict-agent")
    assert isinstance(agent, HandoffAgent)
    assert len(agent.settings.mcp_settings) == 2
    assert agent.settings.model_settings is not None
    assert agent.settings.model_settings["temperature"] == 0.7
    assert agent.settings.model_settings["max_tokens"] == 2000


@pytest.mark.asyncio
async def test_update_config_single_field(registry: DefaultAgentRegistry, default_settings: AgentSettings):
    """Test updating a single field of an existing agent."""
    # Create initial agent
    await registry.add_config(
        name="update-test", description="Original description", settings=default_settings, handoff=False
    )

    # Update just the description
    await registry.update_config(name="update-test", description="Updated description")

    # Verify the change
    config = await registry.get_config("update-test")
    assert config is not None
    assert config["description"] == "Updated description"
    assert config["handoff"] is False  # Should remain unchanged
    assert config["settings"]["model"] == "gpt-3.5-turbo"  # Should remain unchanged


@pytest.mark.asyncio
async def test_update_config_multiple_fields(registry: DefaultAgentRegistry, default_settings: AgentSettings):
    """Test updating multiple fields at once."""
    # Create initial agent
    await registry.add_config(
        name="multi-update", description="Original", settings=default_settings, handoff=False, emoji="🤖"
    )

    # Update multiple fields
    await registry.update_config(name="multi-update", description="Updated description", handoff=True, emoji="🚀")

    # Verify all changes
    config = await registry.get_config("multi-update")
    assert config is not None
    assert config["description"] == "Updated description"
    assert config["handoff"] is True
    assert config["emoji"] == "🚀"
    assert config["settings"]["model"] == "gpt-3.5-turbo"  # Should remain unchanged


@pytest.mark.asyncio
async def test_update_config_settings(
    registry: DefaultAgentRegistry, default_settings: AgentSettings, handoff_settings: AgentSettings
):
    """Test updating agent settings."""
    # Create initial agent
    await registry.add_config(
        name="settings-update", description="Test agent", settings=default_settings, handoff=False
    )

    # Verify initial settings
    agent = await registry.create_agent("settings-update")
    assert agent.settings.model == "gpt-3.5-turbo"
    assert agent.settings.instructions == "You are a helpful assistant."

    # Update settings
    await registry.update_config(name="settings-update", settings=handoff_settings)

    # Verify updated settings
    updated_agent = await registry.create_agent("settings-update")
    assert updated_agent.settings.model == "gpt-4"
    assert updated_agent.settings.instructions == "You can handoff to other agents."
    assert updated_agent.settings.human_feedback is False


@pytest.mark.asyncio
async def test_update_config_partial_fields(registry: DefaultAgentRegistry, default_settings: AgentSettings):
    """Test updating with some None values (should not update those fields)."""
    # Create initial agent with all fields
    await registry.add_config(
        name="partial-update", description="Original description", settings=default_settings, handoff=False, emoji="🤖"
    )

    # Update with some None values
    await registry.update_config(
        name="partial-update",
        description="New description",
        settings=None,  # Should not update
        handoff=None,  # Should not update
        emoji="🎯",
    )

    # Verify only specified fields were updated
    config = await registry.get_config("partial-update")
    assert config is not None
    assert config["description"] == "New description"
    assert config["handoff"] is False  # Unchanged
    assert config["emoji"] == "🎯"
    assert config["settings"]["model"] == "gpt-3.5-turbo"  # Unchanged


@pytest.mark.asyncio
async def test_update_config_nonexistent_agent_error(registry: DefaultAgentRegistry):
    """Test that updating a non-existent agent raises ValueError."""
    with pytest.raises(ValueError, match="No agent registered with name 'nonexistent'"):
        await registry.update_config(name="nonexistent", description="New description")


@pytest.mark.asyncio
async def test_update_config_preserves_unchanged_fields(
    registry: DefaultAgentRegistry, default_settings: AgentSettings
):
    """Test that fields not included in update remain unchanged."""
    # Create agent with specific settings
    original_settings = AgentSettings(
        model="gpt-3.5-turbo",
        instructions="Original instructions",
        human_feedback=True,
        model_settings={"temperature": 0.5, "max_tokens": 1000},
        mcp_settings=default_settings.mcp_settings,
    )

    await registry.add_config(
        name="preserve-test", description="Original description", settings=original_settings, handoff=False, emoji="🤖"
    )

    # Update only description
    await registry.update_config(name="preserve-test", description="New description")

    # Verify all other fields remain unchanged
    config = await registry.get_config("preserve-test")
    assert config is not None
    assert config["description"] == "New description"
    assert config["handoff"] is False
    assert config["emoji"] == "🤖"
    assert config["settings"]["model"] == "gpt-3.5-turbo"
    assert config["settings"]["instructions"] == "Original instructions"
    assert config["settings"]["human_feedback"] is True
    assert config["settings"]["model_settings"]["temperature"] == 0.5
    assert config["settings"]["model_settings"]["max_tokens"] == 1000


@pytest.mark.asyncio
async def test_update_config_emoji_field(registry: DefaultAgentRegistry, default_settings: AgentSettings):
    """Test updating emoji field specifically."""
    # Create agent without emoji
    await registry.add_config(name="emoji-test", description="Test agent", settings=default_settings, handoff=False)

    # Verify no emoji initially
    emoji = await registry.get_emoji("emoji-test")
    assert emoji is None

    # Update to add emoji
    await registry.update_config(name="emoji-test", emoji="🎯")

    # Verify emoji was added
    emoji = await registry.get_emoji("emoji-test")
    assert emoji == "🎯"

    # Update emoji to different value
    await registry.update_config(name="emoji-test", emoji="🚀")

    # Verify emoji was changed
    emoji = await registry.get_emoji("emoji-test")
    assert emoji == "🚀"
