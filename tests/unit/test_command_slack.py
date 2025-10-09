import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from hygroup.connect import ComposioConnector
from hygroup.gateway.slack import SlackGateway
from hygroup.session import SessionFactory
from hygroup.user.settings import CommandNotFoundError, SettingsStore


@pytest.fixture
def session_factory(command_store):
    """Create a mock session factory for testing."""
    factory = MagicMock(spec=SessionFactory)
    factory.request_handler = MagicMock()
    factory.settings_store = command_store
    return factory


@pytest.fixture
def composio_connector():
    """Create a mock composio connector for testing."""
    connector = MagicMock(spec=ComposioConnector)
    return connector


@pytest.fixture
def command_store():
    """Create a mock command store for testing."""
    store = AsyncMock(spec=SettingsStore)
    # Mock get_mapping to return test user mapping (synchronous method)
    user_mapping = {
        "U123": "alice",
        "U456": "bob",
    }
    store.get_mapping = MagicMock(return_value=user_mapping)
    return store


@pytest.fixture
def slack_gateway(session_factory, composio_connector, monkeypatch):
    """Create a SlackGateway instance with test user mappings."""
    # Set required environment variables
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("SLACK_APP_TOKEN", "test-app-token")
    monkeypatch.setenv("SLACK_APP_USER_ID", "test-app-user-id")

    # Mock the AsyncApp and AsyncSocketModeHandler to avoid real Slack connections
    with (
        patch("hygroup.gateway.slack.gateway.AsyncApp"),
        patch("hygroup.gateway.slack.gateway.AsyncWebClient"),
        patch("hygroup.gateway.slack.gateway.AsyncSocketModeHandler"),
    ):
        gateway = SlackGateway(
            session_factory=session_factory,
            composio_connector=composio_connector,
            handle_permission_requests=False,
        )
        return gateway


class TestSlackCommandHandling:
    """Test SlackGateway command handling functionality."""

    @pytest.mark.asyncio
    async def test_handle_command_list_empty(self, slack_gateway, command_store):
        """Test listing commands when none exist."""
        command_store.get_command_names.return_value = []

        ack = AsyncMock()
        body = {"user_id": "U123", "text": "list"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.get_command_names.assert_called_once_with("alice")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        assert "No saved commands found" in blocks[0]["text"]["text"]

    @pytest.mark.asyncio
    async def test_handle_command_list_with_commands(self, slack_gateway, command_store):
        """Test listing commands when some exist."""
        command_store.get_command_names.return_value = ["cmd1", "cmd2", "cmd3"]

        ack = AsyncMock()
        body = {"user_id": "U123", "text": "list"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.get_command_names.assert_called_once_with("alice")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        text = blocks[0]["text"]["text"]
        assert "cmd1" in text
        assert "cmd2" in text
        assert "cmd3" in text

    @pytest.mark.asyncio
    async def test_handle_command_save(self, slack_gateway, command_store):
        """Test saving a command."""
        command_store.set_command.return_value = None

        ack = AsyncMock()
        body = {"user_id": "U456", "text": "save test-cmd echo hello world"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.set_command.assert_called_once_with("bob", "test-cmd", "echo hello world")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        assert "test-cmd" in blocks[0]["text"]["text"]
        assert "saved successfully" in blocks[0]["text"]["text"]

    @pytest.mark.asyncio
    async def test_handle_command_save_missing_content(self, slack_gateway, command_store):
        """Test saving a command without content."""
        ack = AsyncMock()
        body = {"user_id": "U123", "text": "save test-cmd"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.set_command.assert_not_called()
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        assert "Error" in blocks[0]["text"]["text"]

    @pytest.mark.asyncio
    async def test_handle_command_load(self, slack_gateway, command_store):
        """Test loading a command."""
        command_store.get_command.return_value = "echo hello world"

        ack = AsyncMock()
        body = {"user_id": "U123", "text": "load test-cmd"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.get_command.assert_called_once_with("alice", "test-cmd")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        text = blocks[0]["text"]["text"]
        assert "test-cmd" in text
        assert "echo hello world" in text

    @pytest.mark.asyncio
    async def test_handle_command_load_not_found(self, slack_gateway, command_store):
        """Test loading a non-existent command."""
        command_store.get_command.side_effect = CommandNotFoundError("nonexistent")

        ack = AsyncMock()
        body = {"user_id": "U123", "text": "load nonexistent"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.get_command.assert_called_once_with("alice", "nonexistent")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        assert "not found" in blocks[0]["text"]["text"]

    @pytest.mark.asyncio
    async def test_handle_command_delete(self, slack_gateway, command_store):
        """Test deleting a command."""
        command_store.delete_command.return_value = None

        ack = AsyncMock()
        body = {"user_id": "U456", "text": "delete test-cmd"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.delete_command.assert_called_once_with("bob", "test-cmd")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        assert "test-cmd" in blocks[0]["text"]["text"]
        assert "deleted successfully" in blocks[0]["text"]["text"]

    @pytest.mark.asyncio
    async def test_handle_command_no_args_lists_commands(self, slack_gateway, command_store):
        """Test that no arguments defaults to listing commands."""
        command_store.get_command_names.return_value = ["cmd1", "cmd2"]

        ack = AsyncMock()
        body = {"user_id": "U123", "text": ""}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.get_command_names.assert_called_once_with("alice")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        text = blocks[0]["text"]["text"]
        assert "cmd1" in text
        assert "cmd2" in text

    @pytest.mark.asyncio
    async def test_handle_command_no_args_empty_list(self, slack_gateway, command_store):
        """Test that no arguments with no commands shows empty message."""
        command_store.get_command_names.return_value = []

        ack = AsyncMock()
        body = {"user_id": "U123", "text": ""}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.get_command_names.assert_called_once_with("alice")
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        assert "No saved commands found" in blocks[0]["text"]["text"]

    @pytest.mark.asyncio
    async def test_handle_command_help(self, slack_gateway, command_store):
        """Test help command shows usage information."""
        ack = AsyncMock()
        body = {"user_id": "U123", "text": "help"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        command_store.get_command_names.assert_not_called()
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        text = blocks[0]["text"]["text"]
        assert "Usage" in text
        assert "save" in text
        assert "load" in text
        assert "delete" in text
        assert "list" in text
        assert "help" in text

    @pytest.mark.asyncio
    async def test_handle_command_unknown_operation(self, slack_gateway, command_store):
        """Test handling unknown operation."""
        ack = AsyncMock()
        body = {"user_id": "U123", "text": "unknown operation"}
        respond = AsyncMock()

        await slack_gateway.command_handler.handle_command(ack, body, respond)

        ack.assert_called_once()
        respond.assert_called_once()

        blocks = respond.call_args[1]["blocks"]
        assert "Unknown operation" in blocks[0]["text"]["text"]


@pytest_asyncio.fixture
async def temp_command_store():
    """Create a DefaultCommandStore with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    store = SettingsStore(Path(temp_dir))
    yield store
    # Cleanup
    shutil.rmtree(temp_dir)


class TestSettingsStoreCommands:
    """Test SettingsStore command functionality."""

    @pytest.mark.asyncio
    async def test_save_and_load_command(self, temp_command_store):
        """Test saving and loading a command."""
        command = "echo 'Hello, World!'"
        command_name = "hello"
        username = "alice"

        await temp_command_store.set_command(username, command_name, command)
        loaded = await temp_command_store.get_command(username, command_name)

        assert loaded == command

    @pytest.mark.asyncio
    async def test_load_nonexistent_command(self, temp_command_store):
        """Test loading a command that doesn't exist."""
        with pytest.raises(CommandNotFoundError) as exc_info:
            await temp_command_store.get_command("alice", "nonexistent")
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_command(self, temp_command_store):
        """Test deleting a command."""
        command = "echo test"
        command_name = "test"
        username = "bob"

        await temp_command_store.set_command(username, command_name, command)
        await temp_command_store.delete_command(username, command_name)

        with pytest.raises(CommandNotFoundError):
            await temp_command_store.get_command(username, command_name)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_command(self, temp_command_store):
        """Test deleting a command that doesn't exist."""
        # SettingsStore delete_command doesn't raise for non-existent commands
        await temp_command_store.delete_command("alice", "nonexistent")

    @pytest.mark.asyncio
    async def test_command_names_empty(self, temp_command_store):
        """Test listing command names when none exist."""
        names = await temp_command_store.get_command_names("alice")
        assert names == []

    @pytest.mark.asyncio
    async def test_command_names_multiple(self, temp_command_store):
        """Test listing multiple command names."""
        username = "alice"
        commands = {
            "cmd1": "echo 1",
            "cmd2": "echo 2",
            "cmd-3": "echo 3",
            "cmd_4": "echo 4",
        }

        for name, content in commands.items():
            await temp_command_store.set_command(username, name, content)

        names = await temp_command_store.get_command_names(username)
        assert set(names) == set(commands.keys())

    @pytest.mark.asyncio
    async def test_user_isolation(self, temp_command_store):
        """Test that commands are isolated per user."""
        command = "echo test"
        command_name = "test"

        await temp_command_store.set_command("alice", command_name, command)

        # Bob shouldn't have access to Alice's command
        with pytest.raises(CommandNotFoundError):
            await temp_command_store.get_command("bob", command_name)

        # Bob's command list should be empty
        names = await temp_command_store.get_command_names("bob")
        assert names == []

        # Alice should have the command
        loaded = await temp_command_store.get_command("alice", command_name)
        assert loaded == command
