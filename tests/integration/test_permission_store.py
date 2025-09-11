import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from hygroup.user.settings import SettingsStore


@pytest_asyncio.fixture
async def store():
    """Create a SettingsStore with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    store = SettingsStore(Path(temp_dir))
    yield store
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_get_permission_false_by_default(store):
    """Test that get_permission returns False when no permission is stored."""
    result = await store.get_permission("alice", "bash", "session123")
    assert result is False


@pytest.mark.asyncio
async def test_set_and_get_session_permission(store):
    """Test setting and getting session-specific permission."""
    await store.set_permission("alice", "bash", "session123")

    # Should get permission for same session
    result = await store.get_permission("alice", "bash", "session123")
    assert result is True

    # Should not get permission for different session
    result = await store.get_permission("alice", "bash", "session456")
    assert result is False


@pytest.mark.asyncio
async def test_set_and_get_permanent_permission(store):
    """Test setting and getting permanent permission."""
    await store.set_permission("alice", "bash", None)

    # Should get permission for any session
    result = await store.get_permission("alice", "bash", "session123")
    assert result is True

    result = await store.get_permission("alice", "bash", "different_session")
    assert result is True


@pytest.mark.asyncio
async def test_permanent_overrides_session(store):
    """Test that permanent permission overrides session permission."""
    # Set session permission first
    await store.set_permission("alice", "bash", "session123")

    # Then set permanent permission
    await store.set_permission("alice", "bash", None)

    # Should get permanent permission
    result = await store.get_permission("alice", "bash", "session123")
    assert result is True

    # Also for different sessions
    result = await store.get_permission("alice", "bash", "different_session")
    assert result is True


@pytest.mark.asyncio
async def test_multiple_users_same_tool(store):
    """Test different users can have different permissions for same tool."""
    await store.set_permission("alice", "bash", "session123")
    await store.set_permission("bob", "bash", None)

    # Check alice has session permission
    result = await store.get_permission("alice", "bash", "session123")
    assert result is True

    # Check bob has permanent permission
    result = await store.get_permission("bob", "bash", "session123")
    assert result is True

    # Alice doesn't have permission in different session
    result = await store.get_permission("alice", "bash", "session456")
    assert result is False

    # Bob has permission in any session
    result = await store.get_permission("bob", "bash", "session456")
    assert result is True


@pytest.mark.asyncio
async def test_multiple_tools_same_user(store):
    """Test same user can have different permissions for different tools."""
    await store.set_permission("alice", "bash", "session123")
    await store.set_permission("alice", "python", None)

    # Check bash has session permission
    result = await store.get_permission("alice", "bash", "session123")
    assert result is True

    # Check python has permanent permission
    result = await store.get_permission("alice", "python", "session123")
    assert result is True

    # Python works in any session
    result = await store.get_permission("alice", "python", "different_session")
    assert result is True

    # Bash doesn't work in different session
    result = await store.get_permission("alice", "bash", "different_session")
    assert result is False


@pytest.mark.asyncio
async def test_update_session_permission(store):
    """Test updating session permission."""
    # Set initial session permission
    await store.set_permission("alice", "bash", "session123")

    # Update to same session permission (should be idempotent)
    await store.set_permission("alice", "bash", "session123")

    # Should still work
    result = await store.get_permission("alice", "bash", "session123")
    assert result is True
