import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from hygroup.user import User
from hygroup.user.default.registry import DefaultUserRegistry, RegistryLockedError, UserNotRegisteredError


@pytest_asyncio.fixture
async def registry():
    """Create and unlock an EncryptedUserRegistry with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    registry = DefaultUserRegistry(Path(temp_dir) / "test_registry_encrypted.json")
    await registry.unlock("admin_password")
    yield registry
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_register_and_get_user(registry: DefaultUserRegistry):
    """Test registering a new user and retrieving it."""
    user = User(name="alice", secrets={"api_key": "secret123"})
    await registry.register(user)

    retrieved_user = registry.get_user("alice")
    assert retrieved_user is not None
    assert retrieved_user.name == "alice"
    assert retrieved_user.secrets["api_key"] == "secret123"


@pytest.mark.asyncio
async def test_register_with_password(registry: DefaultUserRegistry):
    """Test registering a user with an initial password."""
    user = User(name="bob")
    await registry.register(user, "bob_password")

    retrieved_user = registry.get_user("bob")
    assert retrieved_user is not None
    assert "password_hash" in retrieved_user.secrets

    # Test authentication with the password
    assert registry.authenticate("bob", "bob_password")
    assert registry.authenticated("bob")


@pytest.mark.asyncio
async def test_authentication_no_password(registry: DefaultUserRegistry):
    """Test that a user with no password authenticates successfully."""
    user = User(name="charlie")
    await registry.register(user)

    assert registry.authenticate("charlie", "any_password")
    assert registry.authenticated("charlie")


@pytest.mark.asyncio
async def test_set_and_change_password(registry: DefaultUserRegistry):
    """Test setting a password for a user who has none, then changing it."""
    user = User(name="dave")
    await registry.register(user)

    # Authenticate without password should work
    assert registry.authenticate("dave")

    # Set initial password
    await registry.set_password("dave", "dave_pass_1")
    # Now authentication without password should fail
    assert not registry.authenticate("dave")
    # And with wrong password
    assert not registry.authenticate("dave", "wrong_pass")
    # But correct one should work
    assert registry.authenticate("dave", "dave_pass_1")

    # Change password
    await registry.set_password("dave", "dave_pass_2")
    # Old password should fail
    assert not registry.authenticate("dave", "dave_pass_1")
    # New one should work
    assert registry.authenticate("dave", "dave_pass_2")


@pytest.mark.asyncio
async def test_set_secret(registry: DefaultUserRegistry):
    """Test setting a new secret for a user."""
    user = User(name="eve", secrets={"key1": "val1"})
    await registry.register(user)

    await registry.set_secret("eve", "key2", "val2")

    retrieved_user = registry.get_user("eve")
    assert retrieved_user is not None
    assert retrieved_user.secrets["key1"] == "val1"
    assert retrieved_user.secrets["key2"] == "val2"


@pytest.mark.asyncio
async def test_deauthenticate(registry: DefaultUserRegistry):
    """Test deauthenticating a user."""
    user = User(name="frank")
    await registry.register(user, "frank_pass")

    assert registry.authenticate("frank", "frank_pass")
    assert registry.authenticated("frank")

    assert registry.deauthenticate("frank")
    assert not registry.authenticated("frank")
    # Test that deauthenticating again returns False
    assert not registry.deauthenticate("frank")


@pytest.mark.asyncio
async def test_get_on_nonexistent_user(registry: DefaultUserRegistry):
    """Test that getting info for a non-existent user returns None."""
    assert registry.get_user("no_one") is None
    assert registry.get_secrets("no_one") is None


@pytest.mark.asyncio
async def test_set_secret_on_nonexistent_user(registry: DefaultUserRegistry):
    """Test that setting a secret for a non-existent user raises an error."""
    with pytest.raises(UserNotRegisteredError):
        await registry.set_secret("no_one", "key", "value")


@pytest.mark.asyncio
async def test_operations_on_locked_registry():
    """Test that operations fail on a locked registry."""
    temp_dir = tempfile.mkdtemp()
    locked_registry = DefaultUserRegistry(Path(temp_dir) / "locked.json")

    with pytest.raises(RegistryLockedError):
        locked_registry.get_user("any")
    with pytest.raises(RegistryLockedError):
        await locked_registry.register(User(name="any"))

    # Unlock and verify it works
    await locked_registry.unlock("admin_pass")
    await locked_registry.register(User(name="test"))
    user = locked_registry.get_user("test")
    assert user is not None
    assert user.name == "test"

    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_persistence_across_instances(registry: DefaultUserRegistry):
    """Test that data persists and can be decrypted by a new instance."""
    user = User(name="grace", secrets={"persistent_key": "persistent_value"})
    await registry.register(user, "grace_pass")

    # Create a new registry instance pointing to the same file
    registry_path = registry.registry_path
    registry2 = DefaultUserRegistry(registry_path)

    # Should be locked
    with pytest.raises(RegistryLockedError):
        registry2.get_user("grace")

    # Unlock with the correct password
    await registry2.unlock("admin_password")

    # Verify data
    retrieved_user = registry2.get_user("grace")
    assert retrieved_user is not None
    assert retrieved_user.secrets["persistent_key"] == "persistent_value"

    # Authenticate
    assert registry2.authenticate("grace", "grace_pass")


@pytest.mark.asyncio
async def test_unlock_with_wrong_password(registry: DefaultUserRegistry):
    """Test that unlocking with the wrong password fails."""
    user = User(name="heidi")
    await registry.register(user)

    registry_path = registry.registry_path
    registry2 = DefaultUserRegistry(registry_path)

    with pytest.raises(ValueError, match="Failed to decrypt database"):
        await registry2.unlock("wrong_admin_password")


@pytest.mark.asyncio
async def test_get_mappings(registry: DefaultUserRegistry):
    """Test retrieving gateway-to-user mappings."""
    # Test on empty registry should return empty dict
    assert registry.get_mappings("github") == {}
    assert registry.get_mappings("slack") == {}

    # Register users with different mapping configurations
    user1 = User(name="user1", mappings={"github": "gh-user1", "slack": "slack-user1"})
    user2 = User(name="user2", mappings={"github": "gh-user2"})
    user3 = User(name="user3")  # no mappings
    user4 = User(name="user4", mappings={"slack": "slack-user4"})

    await registry.register(user1)
    await registry.register(user2)
    await registry.register(user3)
    await registry.register(user4)

    # Test for 'github' gateway
    github_mappings = registry.get_mappings("github")
    assert github_mappings == {"gh-user1": "user1", "gh-user2": "user2"}

    # Test for 'slack' gateway
    slack_mappings = registry.get_mappings("slack")
    assert slack_mappings == {"slack-user1": "user1", "slack-user4": "user4"}

    # Test with invalid gateway
    with pytest.raises(ValueError, match="Invalid gateway: invalid_gateway"):
        registry.get_mappings("invalid_gateway")
