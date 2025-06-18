"""Test suite for AgentFactory implementation."""

import os
from pathlib import Path
from typing import Any, Iterator

import pytest
from dotenv import load_dotenv

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
def model_settings(api_key) -> dict[str, Any]:
    """Provide model settings with API key if available."""
    return {"api_key": api_key} if api_key else {}


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
    assert hasattr(registry, "db")


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
async def test_persistence_across_factory_instances(test_agents_dir: Path, default_settings: AgentSettings):
    """Test that data persists across different factory instances."""
    registry_path = Path(test_agents_dir) / "registry.json"
    factory1 = DefaultAgentRegistry(registry_path)
    await factory1.add_config(
        name="persistent-agent", description="Persistent agent", settings=default_settings, handoff=False
    )

    factory2 = DefaultAgentRegistry(registry_path)
    descriptions = await factory2.get_descriptions()
    assert descriptions == {"persistent-agent": "Persistent agent"}

    agent = await factory2.create_agent("persistent-agent")
    assert agent.name == "persistent-agent"
