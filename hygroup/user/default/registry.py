import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Optional

import aiofiles
import aiofiles.os
import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from hygroup.user.base import User, UserRegistry


class RegistryLockedError(Exception):
    """Raised when an operation is attempted on a locked registry."""


class UserNotRegisteredError(Exception):
    """Raised when a user is not found in the registry."""


class UserAlreadyRegisteredError(Exception):
    """Raised when attempting to register an existing username."""


class DefaultUserRegistry(UserRegistry):
    """A user registry that encrypts user data at rest with an admin password.

    **THIS IS A REFERENCE IMPLEMENTATION FOR EXPERIMENTATION, DO NOT USE IN PRODUCTION.**
    """

    def __init__(self, registry_path: Path | str = Path(".data", "users", "registry.bin")):
        self.registry_path = Path(registry_path)
        self._salt: Optional[bytes] = None
        self._key: Optional[bytes] = None
        self._data: Optional[dict] = None
        self._authenticated_users: set[str] = set()
        self._lock = asyncio.Lock()

    async def unlock(self, admin_password: str):
        """Unlock the registry by decrypting the database with the admin password."""
        if self._key is not None:
            return  # Already unlocked

        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.registry_path.exists():
            # First time setup: create a new salt, key, and empty DB
            self._salt = os.urandom(16)
            self._key = self._derive_key(admin_password, self._salt)
            self._data = {}
            await self._save()
            return

        async with aiofiles.open(self.registry_path, "rb") as db_file:
            contents = await db_file.read()

        self._salt = contents[:16]
        encrypted_db = contents[16:]

        self._key = self._derive_key(admin_password, self._salt)  # type: ignore

        try:
            f = Fernet(self._key)
            decrypted_db_bytes = f.decrypt(encrypted_db)
            self._data = json.loads(decrypted_db_bytes)
        except InvalidToken:
            # Clear state on failure to prevent partial access
            self._key = None
            self._salt = None
            self._data = None
            raise ValueError("Failed to decrypt database. The admin password may be incorrect.")

    async def register(self, user: User, password: str | None = None):
        data = self._check_unlocked()
        if user.name in data:
            raise UserAlreadyRegisteredError(f"User '{user.name}' already exists.")

        user_doc = {"name": user.name, "secrets": user.secrets.copy(), "mappings": user.mappings.copy()}

        if password:
            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            user_doc["secrets"]["password_hash"] = base64.b64encode(hashed_password).decode("utf-8")  # type: ignore

        data[user.name] = user_doc
        await self._save()

    def get_user(self, username: str) -> User | None:
        data = self._check_unlocked()
        if username not in data:
            return None

        user_doc = data[username]
        return User(name=user_doc["name"], secrets=user_doc["secrets"], mappings=user_doc.get("mappings", {}))

    def get_mappings(self, gateway: str) -> dict[str, str]:
        data = self._check_unlocked()
        if gateway not in ["slack", "github", "terminal"]:
            raise ValueError(f"Invalid gateway: {gateway}. Must be 'slack' or 'github'.")

        mappings = {}
        for username, user_doc in data.items():
            if gateway_username := user_doc["mappings"].get(gateway):
                mappings[gateway_username] = username
        return mappings

    def get_secrets(self, username: str) -> dict[str, str] | None:
        data = self._check_unlocked()
        if username not in data:
            return None

        return data[username].get("secrets", {}).copy()

    async def set_secret(self, username: str, key: str, value: str):
        data = self._check_unlocked()
        if username not in data:
            raise UserNotRegisteredError(f"User '{username}' not found.")

        data[username]["secrets"][key] = value
        await self._save()

    async def delete_secret(self, username: str, key: str):
        data = self._check_unlocked()
        if username not in data:
            raise UserNotRegisteredError(f"User '{username}' not found.")

        data[username]["secrets"].pop(key, None)
        await self._save()

    async def set_password(self, username: str, new_password: str):
        hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
        await self.set_secret(username, "password_hash", base64.b64encode(hashed_password).decode("utf-8"))

    def authenticate(self, username: str, password: str | None = None) -> bool:
        data = self._check_unlocked()
        if username not in data:
            return True  # only verify registered users

        secrets = data[username].get("secrets", {})
        stored_hash_b64 = secrets.get("password_hash")

        if stored_hash_b64 is None:
            # No password set for user, authentication
            # succeeds with any password provided
            self._authenticated_users.add(username)
            return True

        if password is None:
            return False  # Password required but not provided

        stored_hash = base64.b64decode(stored_hash_b64.encode("utf-8"))
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            self._authenticated_users.add(username)
            return True

        return False

    def deauthenticate(self, username: str) -> bool:
        if username in self._authenticated_users:
            self._authenticated_users.remove(username)
            return True
        return False

    def authenticated(self, username: str) -> bool:
        return username in self._authenticated_users

    async def _save(self):
        """Encrypt the in-memory database and save it to disk."""
        data = self._check_unlocked()
        f = Fernet(self._key)
        data_to_encrypt = json.dumps(data).encode("utf-8")
        encrypted_data = f.encrypt(data_to_encrypt)
        temp_path = self.registry_path.with_suffix(".tmp")

        async with self._lock:
            async with aiofiles.open(temp_path, "wb") as db_file:
                await db_file.write(self._salt + encrypted_data)
            await aiofiles.os.replace(temp_path, self.registry_path)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def _check_unlocked(self) -> dict:
        """Raise an error if the registry is not unlocked."""
        if self._salt is None or self._key is None or self._data is None:
            raise RegistryLockedError("Registry is locked. Please unlock() with admin password first.")
        return self._data
