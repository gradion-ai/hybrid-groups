import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from hygroup.user.settings import SettingsStore


@pytest_asyncio.fixture
async def settings_store():
    """Create a SettingsStore with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    store = SettingsStore(Path(temp_dir))
    yield store
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_get_command_names_empty_user(settings_store: SettingsStore):
    """Test get_command_names returns empty list for non-existent user."""
    result = await settings_store.get_command_names("nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_set_and_get_command(settings_store: SettingsStore):
    """Test setting and getting commands."""
    command_content = "# Test Command\nThis is a test command."

    await settings_store.set_command("alice", "test_command", command_content)

    # Should appear in command names
    command_names = await settings_store.get_command_names("alice")
    assert "test_command" in command_names

    # Should retrieve the same content
    retrieved_content = await settings_store.get_command("alice", "test_command")
    assert retrieved_content == command_content


@pytest.mark.asyncio
async def test_get_nonexistent_command(settings_store: SettingsStore):
    """Test getting a command that doesn't exist raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Command 'nonexistent' not found for user 'alice'"):
        await settings_store.get_command("alice", "nonexistent")


@pytest.mark.asyncio
async def test_set_command_invalid_name(settings_store: SettingsStore):
    """Test that invalid command names raise ValueError."""
    invalid_names = ["test@cmd", "test.cmd", "test cmd", "test/cmd", "test!", "test$", ""]

    for invalid_name in invalid_names:
        with pytest.raises(ValueError) as exc_info:
            await settings_store.set_command("alice", invalid_name, "test content")
        assert "Invalid command name" in str(exc_info.value)
        assert "Only alphanumeric characters, underscores, and hyphens are allowed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_set_command_valid_names(settings_store: SettingsStore):
    """Test that valid command names work correctly."""
    valid_names = ["test", "test_cmd", "test-cmd", "test123", "Test", "CMD_TEST", "cmd-123"]

    for valid_name in valid_names:
        # Should not raise
        await settings_store.set_command("alice", valid_name, "test content")

        # Should be able to retrieve it
        content = await settings_store.get_command("alice", valid_name)
        assert content == "test content"


@pytest.mark.asyncio
async def test_multiple_commands_sorted(settings_store: SettingsStore):
    """Test multiple commands are returned sorted."""
    await settings_store.set_command("alice", "zebra", "zebra content")
    await settings_store.set_command("alice", "alpha", "alpha content")
    await settings_store.set_command("alice", "beta", "beta content")

    command_names = await settings_store.get_command_names("alice")
    assert command_names == ["alpha", "beta", "zebra"]


@pytest.mark.asyncio
async def test_delete_command(settings_store: SettingsStore):
    """Test deleting commands."""
    await settings_store.set_command("alice", "test_command", "test content")

    # Verify it exists
    command_names = await settings_store.get_command_names("alice")
    assert "test_command" in command_names

    # Delete it
    await settings_store.delete_command("alice", "test_command")

    # Should be gone
    command_names = await settings_store.get_command_names("alice")
    assert "test_command" not in command_names


@pytest.mark.asyncio
async def test_delete_nonexistent_command(settings_store: SettingsStore):
    """Test deleting a nonexistent command doesn't raise error."""
    # Should not raise
    await settings_store.delete_command("alice", "nonexistent")


@pytest.mark.asyncio
async def test_command_storage_in_subdirectory(settings_store: SettingsStore):
    """Test that commands are stored in a commands subdirectory."""
    await settings_store.set_command("alice", "test_command", "content")

    # Verify commands are stored in commands subdirectory
    commands_dir = settings_store.root_path / "alice" / "commands"
    command_file = commands_dir / "test_command.md"
    assert command_file.exists()

    # Verify the file structure
    user_dir = settings_store.root_path / "alice"
    assert user_dir.exists()
    assert commands_dir.exists()


@pytest.mark.asyncio
async def test_get_preferences_nonexistent(settings_store: SettingsStore):
    """Test get_preferences returns None for nonexistent user."""
    result = await settings_store.get_preferences("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_preferences(settings_store: SettingsStore):
    """Test setting and getting preferences."""
    preferences_md = "# My Preferences\n\n- Theme: dark\n- Language: en"

    await settings_store.set_preferences("alice", preferences_md)

    # Should retrieve the same markdown
    retrieved = await settings_store.get_preferences("alice")
    assert retrieved == preferences_md

    # Should be cached
    assert "alice" in settings_store._preferences
    assert settings_store._preferences["alice"] == preferences_md


@pytest.mark.asyncio
async def test_preferences_caching(settings_store: SettingsStore):
    """Test that preferences are cached correctly."""
    preferences_md = "# Settings\n\nsetting: value"

    await settings_store.set_preferences("alice", preferences_md)

    # First call should load from file and cache
    result1 = await settings_store.get_preferences("alice")
    assert result1 == preferences_md

    # Second call should use cache (modify cache to verify)
    settings_store._preferences["alice"] = "# Modified Cache\n\ncached: true"
    result2 = await settings_store.get_preferences("alice")
    assert result2 is not None and "cached: true" in result2


@pytest.mark.asyncio
async def test_set_preferences_any_content(settings_store: SettingsStore):
    """Test setting any markdown content works."""
    # Any valid string should work as preferences are now markdown
    await settings_store.set_preferences("alice", "any content here")
    result = await settings_store.get_preferences("alice")
    assert result == "any content here"


@pytest.mark.asyncio
async def test_delete_preferences(settings_store: SettingsStore):
    """Test deleting preferences."""
    preferences_md = "# My Settings\n\nkey: value"

    await settings_store.set_preferences("alice", preferences_md)

    # Verify it exists
    result = await settings_store.get_preferences("alice")
    assert result == preferences_md

    # Delete it
    await settings_store.delete_preferences("alice")

    # Should be None
    result = await settings_store.get_preferences("alice")
    assert result is None

    # Cache should show None
    assert settings_store._preferences["alice"] is None


@pytest.mark.asyncio
async def test_get_permission_no_permissions(settings_store: SettingsStore):
    """Test get_permission returns False when no permissions exist."""
    result = await settings_store.get_permission("alice", "bash", "session123")
    assert result is False


@pytest.mark.asyncio
async def test_get_permission_default_allowed_tools(settings_store: SettingsStore):
    """Test that default allowed tools return True without explicit permissions."""
    # Default allowed tools should return True even without stored permissions
    assert await settings_store.get_permission("alice", "run_agent", "session123") is True
    assert await settings_store.get_permission("alice", "ask_user", "session123") is True
    assert await settings_store.get_permission("alice", "final_result", "session123") is True

    # Non-allowed tools should still require explicit permissions
    assert await settings_store.get_permission("alice", "bash", "session123") is False


@pytest.mark.asyncio
async def test_get_permission_custom_allowed_tools():
    """Test that custom allowed tools work correctly."""
    import tempfile

    temp_dir = tempfile.mkdtemp()
    custom_store = SettingsStore(Path(temp_dir), allowed_tools=["custom_tool", "another_tool"])

    try:
        # Custom allowed tools should return True
        assert await custom_store.get_permission("alice", "custom_tool", "session123") is True
        assert await custom_store.get_permission("alice", "another_tool", "session123") is True

        # Default allowed tools should not be allowed anymore
        assert await custom_store.get_permission("alice", "run_agent", "session123") is False
        assert await custom_store.get_permission("alice", "ask_user", "session123") is False

        # Non-allowed tools should require explicit permissions
        assert await custom_store.get_permission("alice", "bash", "session123") is False
    finally:
        import shutil

        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_get_permission_allowed_tools_override_explicit_permissions(settings_store: SettingsStore):
    """Test that allowed tools return True even if no explicit permission is set."""
    # Even though we haven't set any permissions for run_agent, it should return True
    assert await settings_store.get_permission("alice", "run_agent", "session123") is True

    # But if we set explicit permission for a non-allowed tool, that should work too
    await settings_store.set_permission("alice", "bash", "session123")
    assert await settings_store.get_permission("alice", "bash", "session123") is True
    assert await settings_store.get_permission("alice", "bash", "different_session") is False


@pytest.mark.asyncio
async def test_set_and_get_permanent_permission(settings_store: SettingsStore):
    """Test setting and getting permanent permissions."""
    await settings_store.set_permission("alice", "bash", None)  # None = permanent

    # Should have permission in any session
    assert await settings_store.get_permission("alice", "bash", "session123") is True
    assert await settings_store.get_permission("alice", "bash", "different_session") is True


@pytest.mark.asyncio
async def test_set_and_get_session_permission(settings_store: SettingsStore):
    """Test setting and getting session-specific permissions."""
    await settings_store.set_permission("alice", "bash", "session123")

    # Should have permission only in that session
    assert await settings_store.get_permission("alice", "bash", "session123") is True
    assert await settings_store.get_permission("alice", "bash", "different_session") is False


@pytest.mark.asyncio
async def test_permanent_overrides_session(settings_store: SettingsStore):
    """Test that permanent permission works regardless of session."""
    # Set session permission first
    await settings_store.set_permission("alice", "bash", "session123")

    # Then set permanent permission
    await settings_store.set_permission("alice", "bash", None)

    # Should have permanent permission
    assert await settings_store.get_permission("alice", "bash", "session123") is True
    assert await settings_store.get_permission("alice", "bash", "any_session") is True


@pytest.mark.asyncio
async def test_multiple_tools_and_sessions(settings_store: SettingsStore):
    """Test multiple tools and sessions."""
    # Set different permissions
    await settings_store.set_permission("alice", "bash", "session1")
    await settings_store.set_permission("alice", "python", None)  # permanent
    await settings_store.set_permission("alice", "git", "session2")

    # Test bash - session specific
    assert await settings_store.get_permission("alice", "bash", "session1") is True
    assert await settings_store.get_permission("alice", "bash", "session2") is False

    # Test python - permanent
    assert await settings_store.get_permission("alice", "python", "session1") is True
    assert await settings_store.get_permission("alice", "python", "session2") is True
    assert await settings_store.get_permission("alice", "python", "any_session") is True

    # Test git - different session
    assert await settings_store.get_permission("alice", "git", "session1") is False
    assert await settings_store.get_permission("alice", "git", "session2") is True


@pytest.mark.asyncio
async def test_multiple_users(settings_store: SettingsStore):
    """Test different users have isolated permissions."""
    await settings_store.set_permission("alice", "bash", None)  # permanent
    await settings_store.set_permission("bob", "bash", "session123")  # session only

    # Alice has permanent permission
    assert await settings_store.get_permission("alice", "bash", "any_session") is True

    # Bob has session-specific permission
    assert await settings_store.get_permission("bob", "bash", "session123") is True
    assert await settings_store.get_permission("bob", "bash", "different_session") is False

    # Users don't affect each other
    await settings_store.set_permission("bob", "python", None)  # permanent for bob
    assert await settings_store.get_permission("alice", "python", "any_session") is False


@pytest.mark.asyncio
async def test_permissions_caching(settings_store: SettingsStore):
    """Test that permissions are cached correctly."""
    await settings_store.set_permission("alice", "bash", None)

    # Should be cached
    assert "alice" in settings_store._permissions
    user_perms = settings_store._permissions["alice"]
    assert "bash" in user_perms["permanent"]


@pytest.mark.asyncio
async def test_duplicate_permissions(settings_store: SettingsStore):
    """Test that duplicate permissions are not added."""
    await settings_store.set_permission("alice", "bash", None)
    await settings_store.set_permission("alice", "bash", None)  # Duplicate

    user_perms = settings_store._permissions["alice"]
    # Should only have one instance of "bash"
    assert user_perms["permanent"].count("bash") == 1


@pytest.mark.asyncio
async def test_session_duplicate_permissions(settings_store: SettingsStore):
    """Test that duplicate session permissions are not added."""
    await settings_store.set_permission("alice", "bash", "session123")
    await settings_store.set_permission("alice", "bash", "session123")  # Duplicate

    user_perms = settings_store._permissions["alice"]
    session_perms = user_perms["sessions"]["session123"]
    # Should only have one instance of "bash"
    assert session_perms.count("bash") == 1


@pytest.mark.asyncio
async def test_persistence_across_instances(settings_store: SettingsStore):
    """Test that data persists across store instances."""
    # Set up data
    await settings_store.set_command("alice", "test_cmd", "test content")
    await settings_store.set_preferences("alice", "# My Preferences\n\ntheme: dark")
    await settings_store.set_permission("alice", "bash", None)
    await settings_store.set_permission("bob", "python", "session123")

    # Create new store instance with same path
    store2 = SettingsStore(settings_store.root_path)

    # Test commands persist
    command_names = await store2.get_command_names("alice")
    assert "test_cmd" in command_names
    content = await store2.get_command("alice", "test_cmd")
    assert content == "test content"

    # Test preferences persist
    prefs = await store2.get_preferences("alice")
    assert prefs == "# My Preferences\n\ntheme: dark"

    # Test permissions persist
    assert await store2.get_permission("alice", "bash", "any_session") is True
    assert await store2.get_permission("bob", "python", "session123") is True
    assert await store2.get_permission("bob", "python", "other_session") is False


@pytest.mark.asyncio
async def test_mixed_operations(settings_store: SettingsStore):
    """Test mixed operations on the same user directory."""
    # Set up commands, preferences, and permissions for same user
    await settings_store.set_command("alice", "deploy", "deployment script")
    await settings_store.set_preferences("alice", "# Settings\n\nnotifications: true")
    await settings_store.set_permission("alice", "docker", None)

    # Verify all data coexists
    commands = await settings_store.get_command_names("alice")
    assert "deploy" in commands

    prefs = await settings_store.get_preferences("alice")
    assert prefs is not None and "notifications: true" in prefs

    has_perm = await settings_store.get_permission("alice", "docker", "session123")
    assert has_perm is True

    # User directory should contain all files
    user_dir = settings_store.root_path / "alice"
    assert (user_dir / "commands" / "deploy.md").exists()
    assert (user_dir / "preferences.md").exists()
    assert (user_dir / "permissions.json").exists()


@pytest.mark.asyncio
async def test_edge_cases(settings_store: SettingsStore):
    """Test edge cases with special characters and empty strings."""
    # Special characters in usernames and command names
    await settings_store.set_command("user@domain.com", "cmd-with-dashes", "content")
    commands = await settings_store.get_command_names("user@domain.com")
    assert "cmd-with-dashes" in commands

    # Empty session ID for session permissions
    await settings_store.set_permission("alice", "bash", "")
    assert await settings_store.get_permission("alice", "bash", "") is True
    assert await settings_store.get_permission("alice", "bash", "other") is False


@pytest.mark.asyncio
async def test_atomic_writes(settings_store: SettingsStore):
    """Test that writes are atomic using temp files."""
    # This is more of a verification that the pattern is followed
    # The actual atomicity would be tested in more complex scenarios
    await settings_store.set_command("alice", "test", "content")

    # File should exist and not have .tmp extension
    user_dir = settings_store.root_path / "alice"
    commands_dir = user_dir / "commands"
    assert (commands_dir / "test.md").exists()
    assert not (commands_dir / "test.md.tmp").exists()
