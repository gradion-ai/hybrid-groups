import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from hygroup.user.secrets import SecretsStore, SecretsStoreLocked


@pytest_asyncio.fixture
async def secrets_store():
    """Create a SecretsStore with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    store = SecretsStore(Path(temp_dir))
    yield store
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def unlocked_secrets_store():
    """Create and unlock a SecretsStore with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    store = SecretsStore(Path(temp_dir))
    await store.unlock("admin_password")
    yield store
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_unlock_new_store(secrets_store: SecretsStore):
    """Test unlocking a new secrets store creates salt file."""
    assert secrets_store._salt is None
    assert secrets_store._key is None
    assert secrets_store._secrets is None

    await secrets_store.unlock("admin_password")

    assert secrets_store._salt is not None
    assert secrets_store._key is not None
    assert secrets_store._secrets == {}

    # Check salt file was created
    salt_path = secrets_store.root_path / "salt.bin"
    assert salt_path.exists()


@pytest.mark.asyncio
async def test_unlock_existing_store(secrets_store: SecretsStore):
    """Test unlocking an existing store loads existing salt."""
    # First unlock to create salt
    await secrets_store.unlock("admin_password")
    original_salt = secrets_store._salt

    # Create new store instance with same path
    store2 = SecretsStore(secrets_store.root_path)
    await store2.unlock("admin_password")

    assert store2._salt == original_salt


@pytest.mark.asyncio
async def test_unlock_wrong_password(secrets_store: SecretsStore):
    """Test unlocking with wrong password after data exists raises ValueError."""
    # First unlock and add some data
    await secrets_store.unlock("admin_password")
    await secrets_store.set_secret("alice", "api_key", "secret123")

    # Create new store instance and try wrong password
    store2 = SecretsStore(secrets_store.root_path)
    with pytest.raises(ValueError, match="Failed to decrypt user secrets"):
        await store2.unlock("wrong_password")


@pytest.mark.asyncio
async def test_get_secrets_when_locked(secrets_store: SecretsStore):
    """Test get_secrets raises exception when store is locked."""
    with pytest.raises(SecretsStoreLocked, match="Secrets store is locked"):
        secrets_store.get_secrets("alice")


@pytest.mark.asyncio
async def test_get_secrets_nonexistent_user(unlocked_secrets_store: SecretsStore):
    """Test get_secrets returns None for nonexistent user."""
    result = unlocked_secrets_store.get_secrets("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_secret(unlocked_secrets_store: SecretsStore):
    """Test setting and getting secrets for a user."""
    await unlocked_secrets_store.set_secret("alice", "api_key", "secret123")
    await unlocked_secrets_store.set_secret("alice", "db_password", "dbpass456")

    secrets = unlocked_secrets_store.get_secrets("alice")
    assert secrets == {"api_key": "secret123", "db_password": "dbpass456"}


@pytest.mark.asyncio
async def test_set_secret_when_locked(secrets_store: SecretsStore):
    """Test set_secret raises exception when store is locked."""
    with pytest.raises(SecretsStoreLocked, match="Secrets store is locked"):
        await secrets_store.set_secret("alice", "api_key", "secret123")


@pytest.mark.asyncio
async def test_delete_secret(unlocked_secrets_store: SecretsStore):
    """Test deleting a secret."""
    await unlocked_secrets_store.set_secret("alice", "api_key", "secret123")
    await unlocked_secrets_store.set_secret("alice", "db_password", "dbpass456")

    await unlocked_secrets_store.delete_secret("alice", "api_key")

    secrets = unlocked_secrets_store.get_secrets("alice")
    assert secrets == {"db_password": "dbpass456"}


@pytest.mark.asyncio
async def test_delete_secret_when_locked(secrets_store: SecretsStore):
    """Test delete_secret raises exception when store is locked."""
    with pytest.raises(SecretsStoreLocked, match="Secrets store is locked"):
        await secrets_store.delete_secret("alice", "api_key")


@pytest.mark.asyncio
async def test_delete_nonexistent_secret(unlocked_secrets_store: SecretsStore):
    """Test deleting a nonexistent secret doesn't raise error."""
    await unlocked_secrets_store.set_secret("alice", "api_key", "secret123")

    # Should not raise
    await unlocked_secrets_store.delete_secret("alice", "nonexistent_key")
    await unlocked_secrets_store.delete_secret("nonexistent_user", "api_key")


@pytest.mark.asyncio
async def test_persistence_across_unlock(secrets_store: SecretsStore):
    """Test that secrets persist across unlock cycles."""
    await secrets_store.unlock("admin_password")
    await secrets_store.set_secret("alice", "api_key", "secret123")
    await secrets_store.set_secret("bob", "token", "token456")

    # Create new store instance and unlock
    store2 = SecretsStore(secrets_store.root_path)
    await store2.unlock("admin_password")

    assert store2.get_secrets("alice") == {"api_key": "secret123"}
    assert store2.get_secrets("bob") == {"token": "token456"}


@pytest.mark.asyncio
async def test_delete_all_secrets_removes_user_directory(unlocked_secrets_store: SecretsStore):
    """Test that deleting all secrets for a user removes their directory."""
    await unlocked_secrets_store.set_secret("alice", "api_key", "secret123")

    user_dir = unlocked_secrets_store.root_path / "alice"
    assert user_dir.exists()

    await unlocked_secrets_store.delete_secret("alice", "api_key")

    # Directory should be removed when no secrets remain
    assert not user_dir.exists()


@pytest.mark.asyncio
async def test_multiple_users(unlocked_secrets_store: SecretsStore):
    """Test managing secrets for multiple users."""
    await unlocked_secrets_store.set_secret("alice", "api_key", "alice_secret")
    await unlocked_secrets_store.set_secret("bob", "api_key", "bob_secret")
    await unlocked_secrets_store.set_secret("alice", "db_password", "alice_db")

    assert unlocked_secrets_store.get_secrets("alice") == {"api_key": "alice_secret", "db_password": "alice_db"}
    assert unlocked_secrets_store.get_secrets("bob") == {"api_key": "bob_secret"}


@pytest.mark.asyncio
async def test_unlock_is_idempotent(secrets_store: SecretsStore):
    """Test that calling unlock multiple times doesn't cause issues."""
    await secrets_store.unlock("admin_password")
    original_key = secrets_store._key

    await secrets_store.unlock("admin_password")  # Second unlock
    assert secrets_store._key == original_key  # Should be same key
