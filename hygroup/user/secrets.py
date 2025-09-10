import base64
import json
import os
from pathlib import Path
from typing import Optional

import aiofiles
import aiofiles.os
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class SecretsStoreLocked(Exception):
    """Raised when an operation is attempted on locked user secrets."""


class SecretsStore:
    def __init__(self, root_path: Path = Path(".data", "users")):
        self.root_path = root_path
        self._secrets: dict[str, dict[str, str]] | None = None
        self._salt: Optional[bytes] = None
        self._key: Optional[bytes] = None

    def get_secrets(self, username: str) -> dict[str, str] | None:
        secrets = self._check_unlocked()
        return secrets.get(username)

    async def set_secret(self, username: str, key: str, value: str):
        secrets = self._check_unlocked()

        if username not in secrets:
            secrets[username] = {}

        secrets[username][key] = value
        await self._save(username)

    async def delete_secret(self, username: str, key: str):
        secrets = self._check_unlocked()

        if username in secrets:
            secrets[username].pop(key, None)
            await self._save(username)

    async def unlock(self, admin_password: str):
        if self._key is not None:
            return  # Already unlocked

        await aiofiles.os.makedirs(self.root_path, exist_ok=True)
        salt_path = self.root_path / "salt.bin"

        if not salt_path.exists():
            # First time setup: create a new salt
            self._salt = os.urandom(16)
            async with aiofiles.open(salt_path, "wb") as salt_file:
                await salt_file.write(self._salt)
        else:
            # Load existing salt
            async with aiofiles.open(salt_path, "rb") as salt_file:
                self._salt = await salt_file.read()

        self._key = self._derive_key(admin_password, self._salt)  # type: ignore
        self._secrets = {}

        # Load and decrypt secrets from all user directories
        for user_dir in self.root_path.iterdir():
            if user_dir.is_dir():
                secrets_file = user_dir / "secrets.bin"

                if not await aiofiles.os.path.exists(secrets_file):
                    continue

                async with aiofiles.open(secrets_file, "rb") as f:
                    encrypted_data = await f.read()

                fernet = Fernet(self._key)

                try:
                    decrypted_data = fernet.decrypt(encrypted_data)
                except InvalidToken:
                    raise ValueError("Failed to decrypt user secrets. The admin password may be incorrect.")

                user_secrets = json.loads(decrypted_data.decode("utf-8"))
                self._secrets[user_dir.name] = user_secrets

    async def _save(self, username: str):
        user_dir = self.root_path / username
        secrets_file = user_dir / "secrets.bin"

        # _save is only called after _check_unlocked, so _secrets is guaranteed to be non-None
        assert self._secrets is not None
        user_secrets = self._secrets.get(username, {})

        if not user_secrets:
            # No secrets for user, delete the file if it exists
            if secrets_file.exists():
                await aiofiles.os.remove(secrets_file)
                # Remove directory if empty
                try:
                    user_dir.rmdir()
                except OSError:
                    pass  # Directory not empty or other issue
            return

        # Create user directory if it doesn't exist
        await aiofiles.os.makedirs(user_dir, exist_ok=True)

        # Encrypt and save the secrets
        secrets_json = json.dumps(user_secrets)
        fernet = Fernet(self._key)
        encrypted_data = fernet.encrypt(secrets_json.encode("utf-8"))

        # Atomic write using temp file
        temp_file = secrets_file.with_suffix(".tmp")
        async with aiofiles.open(temp_file, "wb") as f:
            await f.write(encrypted_data)
        await aiofiles.os.replace(temp_file, secrets_file)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def _check_unlocked(self) -> dict[str, dict[str, str]]:
        if self._secrets is None or self._salt is None or self._key is None:
            raise SecretsStoreLocked("Secrets store is locked. Please unlock() with admin password first.")
        return self._secrets
