import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from hygroup.user.default.permission import DefaultPermissionStore


@pytest_asyncio.fixture
async def store():
    """Create a DefaultPermissionStore with a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    store = DefaultPermissionStore(Path(temp_dir) / "test_permissions.json")
    yield store
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_get_permission_none_by_default(store):
    """Test that get_permission returns None when no permission is stored."""
    result = await store.get_permission("bash", "alice", "session123")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_session_permission(store):
    """Test setting and getting session-specific permission (level 2)."""
    await store.set_permission("bash", "alice", "session123", 2)

    # Should get permission for same session
    result = await store.get_permission("bash", "alice", "session123")
    assert result == 2

    # Should not get permission for different session
    result = await store.get_permission("bash", "alice", "session456")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_permanent_permission(store):
    """Test setting and getting permanent permission (level 3)."""
    await store.set_permission("bash", "alice", "session123", 3)

    # Should get permission for any session
    result = await store.get_permission("bash", "alice", "session123")
    assert result == 3

    result = await store.get_permission("bash", "alice", "different_session")
    assert result == 3


@pytest.mark.asyncio
async def test_permanent_overrides_session(store):
    """Test that permanent permission overrides session permission."""
    # Set session permission first
    await store.set_permission("bash", "alice", "session123", 2)

    # Then set permanent permission
    await store.set_permission("bash", "alice", "session123", 3)

    # Should get permanent permission (3)
    result = await store.get_permission("bash", "alice", "session123")
    assert result == 3

    # Also for different sessions
    result = await store.get_permission("bash", "alice", "different_session")
    assert result == 3


@pytest.mark.asyncio
async def test_level_0_not_stored(store):
    """Test that level 0 (denied) is not stored."""
    await store.set_permission("bash", "alice", "session123", 0)

    # Should still return None
    result = await store.get_permission("bash", "alice", "session123")
    assert result is None


@pytest.mark.asyncio
async def test_level_1_not_stored(store):
    """Test that level 1 (granted once) is not stored."""
    await store.set_permission("bash", "alice", "session123", 1)

    # Should still return None
    result = await store.get_permission("bash", "alice", "session123")
    assert result is None


@pytest.mark.asyncio
async def test_level_0_does_not_remove_existing(store):
    """Test that setting level 0 does not remove existing permissions."""
    # First set a permanent permission
    await store.set_permission("bash", "alice", "session123", 3)

    # Try to "deny" with level 0
    await store.set_permission("bash", "alice", "session123", 0)

    # Original permission should still exist
    result = await store.get_permission("bash", "alice", "session123")
    assert result == 3


@pytest.mark.asyncio
async def test_multiple_users_same_tool(store):
    """Test different users can have different permissions for same tool."""
    await store.set_permission("bash", "alice", "session123", 2)
    await store.set_permission("bash", "bob", "session123", 3)

    # Check alice has session permission
    result = await store.get_permission("bash", "alice", "session123")
    assert result == 2

    # Check bob has permanent permission
    result = await store.get_permission("bash", "bob", "session123")
    assert result == 3

    # Alice doesn't have permission in different session
    result = await store.get_permission("bash", "alice", "session456")
    assert result is None

    # Bob has permission in any session
    result = await store.get_permission("bash", "bob", "session456")
    assert result == 3


@pytest.mark.asyncio
async def test_multiple_tools_same_user(store):
    """Test same user can have different permissions for different tools."""
    await store.set_permission("bash", "alice", "session123", 2)
    await store.set_permission("python", "alice", "session123", 3)

    # Check bash has session permission
    result = await store.get_permission("bash", "alice", "session123")
    assert result == 2

    # Check python has permanent permission
    result = await store.get_permission("python", "alice", "session123")
    assert result == 3

    # Python works in any session
    result = await store.get_permission("python", "alice", "different_session")
    assert result == 3

    # Bash doesn't work in different session
    result = await store.get_permission("bash", "alice", "different_session")
    assert result is None


@pytest.mark.asyncio
async def test_update_session_permission(store):
    """Test updating session permission."""
    # Set initial session permission
    await store.set_permission("bash", "alice", "session123", 2)

    # Update to different session permission (should upsert)
    await store.set_permission("bash", "alice", "session123", 2)

    # Should still be 2
    result = await store.get_permission("bash", "alice", "session123")
    assert result == 2


@pytest.mark.asyncio
async def test_persistence_across_instances(store):
    """Test that permissions persist across store instances."""
    # Set some permissions
    await store.set_permission("bash", "alice", "session123", 2)
    await store.set_permission("python", "bob", "session456", 3)

    # Create new store instance with same path
    store2 = DefaultPermissionStore(store.store_path)

    # Check permissions persist
    result = await store2.get_permission("bash", "alice", "session123")
    assert result == 2

    result = await store2.get_permission("python", "bob", "any_session")
    assert result == 3


@pytest.mark.asyncio
async def test_session_id_none_for_permanent(store):
    """Test that permanent permissions have session_id as None in storage."""
    await store.set_permission("bash", "alice", "session123", 3)

    # Check internal storage (this is a white-box test)
    from tinydb import Query

    Query_ = Query()
    doc = store._tinydb.get(
        (Query_.tool_name == "bash") & (Query_.username == "alice") & (Query_.session_id == None)  # noqa: E711
    )
    assert doc is not None
    assert doc["permission"] == 3
    assert doc["session_id"] is None


@pytest.mark.asyncio
async def test_permanent_permission_removes_all_existing(store):
    """Test that setting permanent permission removes all existing permissions."""
    # Set multiple session permissions
    await store.set_permission("bash", "alice", "session1", 2)
    await store.set_permission("bash", "alice", "session2", 2)
    await store.set_permission("bash", "alice", "session3", 2)

    # Set permanent permission
    await store.set_permission("bash", "alice", "ignored_session", 3)

    # Check that all documents for this tool/user are removed except the permanent one
    from tinydb import Query

    Query_ = Query()
    docs = store._tinydb.search((Query_.tool_name == "bash") & (Query_.username == "alice"))
    assert len(docs) == 1
    assert docs[0]["permission"] == 3
    assert docs[0]["session_id"] is None


@pytest.mark.asyncio
async def test_edge_cases(store):
    """Test edge cases with empty strings and special characters."""
    # Empty tool name
    await store.set_permission("", "alice", "session123", 2)
    result = await store.get_permission("", "alice", "session123")
    assert result == 2

    # Empty username
    await store.set_permission("bash", "", "session123", 2)
    result = await store.get_permission("bash", "", "session123")
    assert result == 2

    # Empty session_id
    await store.set_permission("bash", "alice", "", 2)
    result = await store.get_permission("bash", "alice", "")
    assert result == 2

    # Special characters in names
    await store.set_permission("tool@#$%", "user!@#", "sess^&*()", 3)
    result = await store.get_permission("tool@#$%", "user!@#", "any_session")
    assert result == 3
