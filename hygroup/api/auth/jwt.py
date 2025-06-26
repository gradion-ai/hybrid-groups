from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from jose import JWTError, jwt

from hygroup.api.config import ApiServerSettings


def create_access_token(username: str, settings: ApiServerSettings) -> str:
    """Create a JWT access token for the given username.

    Args:
        username: The username to encode in the token
        settings: Application settings containing JWT configuration

    Returns:
        The encoded JWT token as a string
    """
    # Calculate expiration time
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiration_days)

    # Create token payload
    to_encode = {"username": username, "exp": expire, "iat": datetime.now(timezone.utc)}

    # Encode and return JWT token
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def verify_token(token: str, settings: ApiServerSettings) -> Dict[str, str]:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token to verify
        settings: Application settings containing JWT configuration

    Returns:
        The decoded token payload as a dictionary

    Raises:
        JWTError: If the token is invalid, expired, or malformed
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise


def get_current_username(token: str, settings: ApiServerSettings) -> Optional[str]:
    """Extract the username from a JWT token.

    Args:
        token: The JWT token to decode
        settings: Application settings containing JWT configuration

    Returns:
        The username from the token, or None if token is invalid
    """
    try:
        payload = verify_token(token, settings)
        username: str = payload.get("username")  # type: ignore
        return username
    except JWTError:
        return None
