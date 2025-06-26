import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hygroup.api.auth.jwt import get_current_username
from hygroup.api.dependencies import SettingsDependency, UserRegistryDependency

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user_from_jwt(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    settings: SettingsDependency,
    user_registry: UserRegistryDependency,
) -> str:
    """Extract and validate current user from JWT token and verify server-side authentication.

    Args:
        credentials: HTTP Bearer token credentials
        settings: Application settings for JWT validation
        user_registry: User registry to check authentication status

    Returns:
        Username of the authenticated user

    Raises:
        HTTPException: If token is invalid, expired, missing, or user is not authenticated
    """
    try:
        # Extract username from JWT token
        username = get_current_username(credentials.credentials, settings)

        if username is None:
            logger.warning("Invalid or expired JWT token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if user is still authenticated in the registry (not logged out)
        if not user_registry.authenticated(username):
            logger.warning(f"User {username} has valid JWT but is not authenticated in registry (logged out)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User session has been terminated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug(f"Successfully authenticated user from JWT: {username}")
        return username

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.warning(f"JWT authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


UserDependency = Annotated[str, Depends(get_current_user_from_jwt)]
