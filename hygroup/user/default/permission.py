import asyncio
from pathlib import Path

from tinydb import Query, TinyDB

from hygroup.user.base import PermissionStore
from hygroup.utils import arun


class DefaultPermissionStore(PermissionStore):
    """TinyDB-based permission store that persists tool permissions for users across sessions."""

    def __init__(self, store_path: Path | str = Path(".data", "users", "permissions.json")):
        """Initialize the permission store with TinyDB storage.

        Args:
            store_path: Path to the permission store file
        """
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

        self._tinydb = TinyDB(str(self.store_path), indent=2)
        self._lock = asyncio.Lock()

    async def get_permission(self, tool_name: str, username: str, session_id: str) -> int | None:
        """Get permission for a tool and user, considering session context.

        Args:
            tool_name: Name of the tool
            username: Username requesting permission
            session_id: Current session ID

        Returns:
            Permission level (2 or 3) if found, None otherwise
        """
        Query_ = Query()

        async with self._lock:
            # First, check for permanent permission (level 3)
            permanent_permission = await arun(
                self._tinydb.get,
                (Query_.tool_name == tool_name) & (Query_.username == username) & (Query_.session_id == None),  # noqa: E711
            )
            if permanent_permission:
                return permanent_permission["permission"]

            # Then check for session-specific permission (level 2)
            session_permission = await arun(
                self._tinydb.get,
                (Query_.tool_name == tool_name) & (Query_.username == username) & (Query_.session_id == session_id),
            )
            if session_permission:
                return session_permission["permission"]

        # No stored permission found
        return None

    async def set_permission(self, tool_name: str, username: str, session_id: str, permission: int):
        """Set permission for a tool and user.

        Only stores permission levels 2 (session) and 3 (always).
        Levels 0 (denied) and 1 (granted once) are not persisted.

        Args:
            tool_name: Name of the tool
            username: Username to set permission for
            session_id: Session ID (used for level 2, ignored for level 3)
            permission: Permission level to set (0-3)
        """
        # Only persist levels 2 and 3
        if permission not in (2, 3):
            return

        Query_ = Query()

        # Prepare the document
        doc = {
            "tool_name": tool_name,
            "username": username,
            "permission": permission,
            "session_id": session_id if permission == 2 else None,
        }

        async with self._lock:
            # For level 3, remove any existing permissions (session or permanent) and insert new
            if permission == 3:
                # Remove all existing permissions for this tool/user combination
                await arun(self._tinydb.remove, (Query_.tool_name == tool_name) & (Query_.username == username))
                # Insert the permanent permission
                await arun(self._tinydb.insert, doc)
            elif permission == 2:
                # For level 2, upsert based on tool/user/session combination
                await arun(
                    self._tinydb.upsert,
                    doc,
                    (Query_.tool_name == tool_name) & (Query_.username == username) & (Query_.session_id == session_id),
                )
