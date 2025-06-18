import base64
import os
from pathlib import Path

import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from tinydb import Query, TinyDB

from hygroup.user.base import User, UserAlreadyExistsError, UserNotAuthenticatedError, UserRegistry
from hygroup.utils import arun


class DefaultUserRegistry(UserRegistry):
    def __init__(self, registry_path: Path | str = Path(".data", "users", "registry.json")):
        """Initialize the registry with TinyDB storage.

        Args:
            registry_path: Path to the registry file
        """
        self._users: dict[str, User] = {}
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(self.registry_path), indent=2)

    async def register(self, user: User, password: str):
        """Register a new user.

        Args:
            user: User object with name and secrets
            password: Password to use for hashing and encryption

        Raises:
            UserAlreadyExistsError: If username already exists
        """
        # Check if user with that username already exists
        UserQuery = Query()
        existing = await arun(self.db.get, UserQuery.name == user.name)
        if existing is not None:
            raise UserAlreadyExistsError(f"User '{user.name}' already exists")

        # Save user to disk
        await self.save_user(user, password)

    async def save_user(self, user: User, password: str):
        """Save user to disk with encrypted secrets and hashed password.

        Args:
            user: User object with name and secrets
            password: Password to use for hashing and encryption
        """
        # Hash password with bcrypt
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt)

        # Generate salt for encryption
        encryption_salt = os.urandom(16)

        # Derive encryption key from password
        key = self._derive_key(password, encryption_salt)
        f = Fernet(key)

        # Encrypt all secrets
        encrypted_secrets = {}
        for secret_name, secret_value in user.secrets.items():
            encrypted = f.encrypt(secret_value.encode("utf-8"))
            # Store salt + encrypted data as base64
            payload = encryption_salt + encrypted
            encrypted_secrets[secret_name] = base64.b64encode(payload).decode("utf-8")

        # Create document for TinyDB
        doc = {
            "name": user.name,
            "password_hash": base64.b64encode(hashed_password).decode("utf-8"),
            "encrypted_secrets": encrypted_secrets,
            "salt": base64.b64encode(encryption_salt).decode("utf-8"),
            "mappings": user.mappings,
        }

        # Insert or update document
        UserQuery = Query()
        await arun(self.db.upsert, doc, UserQuery.name == user.name)

    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user and load their decrypted secrets into memory.

        Args:
            username: Username to authenticate
            password: Password to verify

        Returns:
            True if authentication successful, False otherwise
        """
        # Query user from TinyDB
        UserQuery = Query()
        user_doc = await arun(self.db.get, UserQuery.name == username)

        if user_doc is None:
            return False

        # Verify password with bcrypt
        stored_hash = base64.b64decode(user_doc["password_hash"].encode("utf-8"))
        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return False

        # Decrypt all secrets
        decrypted_secrets = {}
        for secret_name, encrypted_data in user_doc["encrypted_secrets"].items():
            # Decode base64 payload
            payload = base64.b64decode(encrypted_data.encode("utf-8"))
            salt = payload[:16]
            encrypted_secret = payload[16:]

            # Derive key and decrypt
            key = self._derive_key(password, salt)
            f = Fernet(key)

            try:
                decrypted = f.decrypt(encrypted_secret)
                decrypted_secrets[secret_name] = decrypted.decode("utf-8")
            except Exception:
                # Failed to decrypt - password might have changed
                return False

        # Get gateway mappings
        mappings = user_doc.get("mappings", {})

        # Create User object and store in memory
        user = User(name=username, secrets=decrypted_secrets, mappings=mappings)
        self._users[username] = user

        return True

    def get_secrets(self, username: str) -> dict[str, str]:
        """Get all decrypted secrets for an authenticated user.

        Args:
            username: Username to get secrets for

        Returns:
            Dictionary of all secrets (key-value pairs)

        Raises:
            NotAuthenticatedError: If user is not authenticated
        """
        if username not in self._users:
            raise UserNotAuthenticatedError(f"User '{username}' is not authenticated")

        user = self._users[username]
        return user.secrets.copy()

    def get_secret(self, username: str, key: str) -> str:
        """Get a decrypted secret for an authenticated user.

        Args:
            username: Username to get secret for
            key: Secret key to retrieve

        Returns:
            Decrypted secret value

        Raises:
            NotAuthenticatedError: If user is not authenticated
            KeyError: If secret key doesn't exist
        """
        secrets = self.get_secrets(username)
        if key not in secrets:
            raise KeyError(f"Secret '{key}' not found for user '{username}'")
        return secrets[key]

    async def set_secret(self, username: str, key: str, value: str, password: str):
        """Set a secret for an authenticated user.

        Args:
            username: Username to set secret for
            key: Secret key to set
            value: Secret value to store
            password: User's password for re-encryption

        Raises:
            NotAuthenticatedError: If user is not authenticated
        """
        if username not in self._users:
            raise UserNotAuthenticatedError(f"User '{username}' is not authenticated")

        # Update secret in memory
        user = self._users[username]
        user.secrets[key] = value

        # Re-encrypt and save to TinyDB
        await self.save_user(user, password)

    async def delete_secret(self, username: str, key: str, password: str):
        """Delete a secret for an authenticated user.

        Args:
            username: Username to delete secret for
            key: Secret key to delete
            password: User's password for re-encryption

        Raises:
            NotAuthenticatedError: If user is not authenticated
            KeyError: If secret key doesn't exist
        """
        if username not in self._users:
            raise UserNotAuthenticatedError(f"User '{username}' is not authenticated")

        user = self._users[username]
        if key not in user.secrets:
            raise KeyError(f"Secret '{key}' not found for user '{username}'")

        # Remove secret from memory
        del user.secrets[key]

        # Re-encrypt and save to TinyDB
        await self.save_user(user, password)

    async def get_mapping(self, gateway: str) -> dict[str, str]:
        """Get the mapping for a specific gateway from the database.

        Args:
            gateway: The gateway (e.g., 'slack', 'github')

        Returns:
            A dictionary where keys are gateway usernames and values are database usernames.
        """
        all_users = await arun(self.db.all)
        mapping = {}
        for user_doc in all_users:
            user_mapping = user_doc.get("mappings", {})
            if gateway in user_mapping:
                gateway_username = user_mapping[gateway]
                database_username = user_doc["name"]
                mapping[gateway_username] = database_username
        return mapping

    async def deauthenticate(self, username: str) -> bool:
        """Deauthenticate a user by removing them from memory.

        Args:
            username: Username to deauthenticate

        Returns:
            True if user was logged out, False if user wasn't authenticated
        """
        if username in self._users:
            del self._users[username]
            return True
        return False

    def authenticated(self, username: str) -> bool:
        """Check if a user is authenticated.

        Args:
            username: Username to check

        Returns:
            True if user is authenticated, False otherwise
        """
        return username in self._users

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2.

        Args:
            password: Password to derive key from
            salt: Salt for key derivation

        Returns:
            Base64-encoded encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
