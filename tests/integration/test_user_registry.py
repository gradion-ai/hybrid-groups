import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from hygroup.user import User, UserAlreadyExistsError, UserNotAuthenticatedError
from hygroup.user.default import DefaultUserRegistry


@pytest_asyncio.fixture
async def registry():
    """Create a UserRegistry with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    registry = DefaultUserRegistry(Path(temp_dir) / "test_registry.json")
    yield registry
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_register_new_user(registry):
    """Test registering a new user."""
    user = User(name="alice", secrets={"api_key": "secret123"})
    await registry.register(user, "password123")

    # Verify user is not automatically authenticated
    assert not registry.authenticated("alice")


@pytest.mark.asyncio
async def test_register_duplicate_user(registry):
    """Test that registering duplicate username raises error."""
    user1 = User(name="alice", secrets={"key": "value1"})
    await registry.register(user1, "password123")

    user2 = User(name="alice", secrets={"key": "value2"})
    with pytest.raises(UserAlreadyExistsError):
        await registry.register(user2, "password456")


@pytest.mark.asyncio
async def test_authenticate_valid_user(registry):
    """Test authenticating with valid credentials."""
    user = User(name="alice", secrets={"api_key": "secret123", "db_pass": "dbsecret"})
    await registry.register(user, "password123")

    # Authenticate
    success = await registry.authenticate("alice", "password123")
    assert success
    assert registry.authenticated("alice")

    # Verify secrets are accessible
    assert registry.get_secret("alice", "api_key") == "secret123"
    assert registry.get_secret("alice", "db_pass") == "dbsecret"


@pytest.mark.asyncio
async def test_authenticate_invalid_password(registry):
    """Test authenticating with wrong password."""
    user = User(name="alice", secrets={"key": "value"})
    await registry.register(user, "password123")

    success = await registry.authenticate("alice", "wrongpassword")
    assert not success
    assert not registry.authenticated("alice")


@pytest.mark.asyncio
async def test_authenticate_nonexistent_user(registry):
    """Test authenticating non-existent user."""
    success = await registry.authenticate("nobody", "password")
    assert not success


@pytest.mark.asyncio
async def test_get_secret_not_authenticated(registry):
    """Test getting secret when not authenticated."""
    user = User(name="alice", secrets={"key": "value"})
    await registry.register(user, "password123")

    with pytest.raises(UserNotAuthenticatedError):
        registry.get_secret("alice", "key")


@pytest.mark.asyncio
async def test_get_secret_nonexistent_key(registry):
    """Test getting non-existent secret key."""
    user = User(name="alice", secrets={"key1": "value1"})
    await registry.register(user, "password123")
    await registry.authenticate("alice", "password123")

    with pytest.raises(KeyError):
        registry.get_secret("alice", "nonexistent")


@pytest.mark.asyncio
async def test_set_secret(registry):
    """Test setting a new secret for authenticated user."""
    user = User(name="alice", secrets={"key1": "value1"})
    await registry.register(user, "password123")
    await registry.authenticate("alice", "password123")

    # Set new secret
    await registry.set_secret("alice", "key2", "value2")

    # Verify it's accessible
    assert registry.get_secret("alice", "key2") == "value2"

    # Verify it persists after re-authentication
    await registry.deauthenticate("alice")
    await registry.authenticate("alice", "password123")
    assert registry.get_secret("alice", "key2") == "value2"


@pytest.mark.asyncio
async def test_set_secret_not_authenticated(registry):
    """Test set_secret when user is not authenticated."""
    user = User(name="alice", secrets={"key": "value"})
    await registry.register(user, "password123")

    # Try to set secret without authentication
    with pytest.raises(UserNotAuthenticatedError):
        await registry.set_secret("alice", "key2", "value2")


@pytest.mark.asyncio
async def test_update_existing_secret(registry):
    """Test updating an existing secret."""
    user = User(name="alice", secrets={"key1": "value1"})
    await registry.register(user, "password123")
    await registry.authenticate("alice", "password123")

    # Update existing secret
    await registry.set_secret("alice", "key1", "new_value")

    # Verify it's updated
    assert registry.get_secret("alice", "key1") == "new_value"

    # Verify it persists
    await registry.deauthenticate("alice")
    await registry.authenticate("alice", "password123")
    assert registry.get_secret("alice", "key1") == "new_value"


@pytest.mark.asyncio
async def test_delete_secret(registry):
    """Test deleting a secret."""
    user = User(name="alice", secrets={"key1": "value1", "key2": "value2"})
    await registry.register(user, "password123")
    await registry.authenticate("alice", "password123")

    # Delete secret
    await registry.delete_secret("alice", "key1")

    # Verify it's gone
    with pytest.raises(KeyError):
        registry.get_secret("alice", "key1")

    # Verify other secret still exists
    assert registry.get_secret("alice", "key2") == "value2"


@pytest.mark.asyncio
async def test_delete_secret_not_authenticated(registry):
    """Test delete_secret when user is not authenticated."""
    user = User(name="alice", secrets={"key": "value"})
    await registry.register(user, "password123")

    # Try to delete secret without authentication
    with pytest.raises(UserNotAuthenticatedError):
        await registry.delete_secret("alice", "key")


@pytest.mark.asyncio
async def test_delete_secret_nonexistent_key(registry):
    """Test deleting non-existent secret key with session method."""
    user = User(name="alice", secrets={"key1": "value1"})
    await registry.register(user, "password123")
    await registry.authenticate("alice", "password123")

    with pytest.raises(KeyError):
        await registry.delete_secret("alice", "nonexistent")


@pytest.mark.asyncio
async def test_deauthenticate(registry):
    """Test deauthenticate functionality."""
    user = User(name="alice", secrets={"key": "value"})
    await registry.register(user, "password123")
    await registry.authenticate("alice", "password123")

    # Verify authenticated
    assert registry.authenticated("alice")

    # Deauthenticate
    success = await registry.deauthenticate("alice")
    assert success
    assert not registry.authenticated("alice")

    # Try to access secret after deauthenticate
    with pytest.raises(UserNotAuthenticatedError):
        registry.get_secret("alice", "key")


@pytest.mark.asyncio
async def test_deauthenticate_not_authenticated(registry):
    """Test deauthenticating user who isn't authenticated."""
    success = await registry.deauthenticate("nobody")
    assert not success


@pytest.mark.asyncio
async def test_persistence_across_instances(registry):
    """Test that data persists across registry instances."""
    # Register and save user
    user = User(name="alice", secrets={"api_key": "secret123"})
    await registry.register(user, "password123")

    # Create new registry instance with same path
    registry2 = DefaultUserRegistry(registry.registry_path)

    # Authenticate with the new instance
    success = await registry2.authenticate("alice", "password123")
    assert success
    assert registry2.get_secret("alice", "api_key") == "secret123"


@pytest.mark.asyncio
async def test_empty_secrets(registry):
    """Test user with no secrets."""
    user = User(name="alice")
    await registry.register(user, "password123")
    await registry.authenticate("alice", "password123")

    # Should not raise any errors
    with pytest.raises(KeyError):
        registry.get_secret("alice", "nonexistent")
