import logging

from fastapi import APIRouter, HTTPException, status

from hygroup.api.auth.dependencies import UserDependency
from hygroup.api.auth.jwt import create_access_token
from hygroup.api.auth.schemas import LoginRequest, LogoutResponse, TokenResponse
from hygroup.api.dependencies import SettingsDependency, UserRegistryDependency

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    settings: SettingsDependency,
    user_registry: UserRegistryDependency,
) -> TokenResponse:
    logger.info(f"Login attempt for username: {request.username}")

    is_authenticated = await user_registry.authenticate(request.username, request.password)

    if not is_authenticated:
        logger.warning(f"Failed login attempt for username: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(request.username, settings)
    expires_in = settings.jwt_expiration_days * 24 * 60 * 60

    logger.info(f"Successful login for username: {request.username}")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    user: UserDependency,
    user_registry: UserRegistryDependency,
) -> LogoutResponse:
    await user_registry.deauthenticate(user)

    logger.info(f"User logged out: {user}")

    return LogoutResponse(message="Successfully logged out")
