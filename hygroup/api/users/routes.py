import logging
from typing import NoReturn

from fastapi import APIRouter, HTTPException, status

from hygroup.api.auth.dependencies import UserDependency
from hygroup.api.dependencies import UserRegistryDependency
from hygroup.api.users.schemas import (
    MappingResponse,
    MappingsListResponse,
    MessageResponse,
    SecretCreateRequest,
    SecretResponse,
    SecretsListResponse,
    SecretUpdateRequest,
    SecretValueResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_secret_exists(user_registry: UserRegistryDependency, user: str, secret_name: str) -> None:
    """Ensure secret exists, raise 404 if not found."""
    try:
        user_registry.get_secret(user, secret_name)
    except KeyError:
        logger.warning(f"Secret '{secret_name}' not found for user: {user}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret '{secret_name}' not found",
        )


def _ensure_secret_not_exists(user_registry: UserRegistryDependency, user: str, secret_name: str) -> None:
    """Ensure secret doesn't exist, raise 409 if it does."""
    try:
        user_registry.get_secret(user, secret_name)
        logger.warning(f"Secret '{secret_name}' already exists for user: {user}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Secret '{secret_name}' already exists",
        )
    except KeyError:
        pass


def _handle_secret_operation_error(e: Exception, operation: str, user: str, secret_name: str | None = None) -> NoReturn:
    """Handle unexpected errors during secret operations."""
    if secret_name:
        logger.error(f"Failed to {operation} secret '{secret_name}' for user {user}: {str(e)}")
        detail = f"Failed to {operation} secret"
    else:
        logger.error(f"Failed to {operation} for user {user}: {str(e)}")
        detail = f"Failed to {operation}"

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )


@router.get("/info", response_model=UserResponse)
async def get_user_info(
    user: UserDependency,
) -> UserResponse:
    """Get current user information from JWT token."""
    return UserResponse(username=user)


@router.get("/secrets", response_model=SecretsListResponse)
async def get_secrets(
    user: UserDependency,
    user_registry: UserRegistryDependency,
) -> SecretsListResponse:
    """Get list of all secret names for the current user."""
    logger.info(f"Getting secrets list for user: {user}")

    try:
        secrets_dict = user_registry.get_secrets(user)
        secrets = [SecretResponse(name=name) for name in secrets_dict.keys()]

        logger.info(f"Retrieved {len(secrets)} secrets for user: {user}")
        return SecretsListResponse(secrets=secrets)

    except Exception as e:
        _handle_secret_operation_error(e, "retrieve secrets", user)


@router.get("/secrets/{secret_name}/value", response_model=SecretValueResponse)
async def get_secret_value(
    secret_name: str,
    user: UserDependency,
    user_registry: UserRegistryDependency,
) -> SecretValueResponse:
    """Get the value of a specific secret for the current user."""
    logger.info(f"Getting secret value '{secret_name}' for user: {user}")

    try:
        _ensure_secret_exists(user_registry, user, secret_name)
        secret_value = user_registry.get_secret(user, secret_name)

        logger.info(f"Successfully retrieved secret '{secret_name}' for user: {user}")
        return SecretValueResponse(name=secret_name, value=secret_value)

    except HTTPException:
        raise
    except Exception as e:
        _handle_secret_operation_error(e, "retrieve secret value", user, secret_name)


@router.get("/mappings", response_model=MappingsListResponse)
async def get_mappings(
    user: UserDependency,
    user_registry: UserRegistryDependency,
) -> MappingsListResponse:
    """Get list of all mappings for the current user."""
    logger.info(f"Getting mappings for user: {user}")

    try:
        mappings_dict = user_registry.get_mappings(user)
        mappings = [
            MappingResponse(gateway_name=gateway, gateway_username=username)
            for gateway, username in mappings_dict.items()
        ]

        logger.info(f"Retrieved {len(mappings)} mappings for user: {user}")
        return MappingsListResponse(mappings=mappings)

    except Exception as e:
        _handle_secret_operation_error(e, "retrieve mappings", user)


@router.post("/secrets", response_model=MessageResponse)
async def create_secret(
    request: SecretCreateRequest,
    user: UserDependency,
    user_registry: UserRegistryDependency,
) -> MessageResponse:
    """Create a new secret for the current user."""
    logger.info(f"Creating secret '{request.name}' for user: {user}")

    try:
        _ensure_secret_not_exists(user_registry, user, request.name)
        await user_registry.set_secret(user, request.name, request.value)

        logger.info(f"Successfully created secret '{request.name}' for user: {user}")
        return MessageResponse(message=f"Secret '{request.name}' created successfully")

    except HTTPException:
        raise
    except Exception as e:
        _handle_secret_operation_error(e, "create", user, request.name)


@router.put("/secrets/{secret_name}", response_model=MessageResponse)
async def update_secret(
    secret_name: str,
    request: SecretUpdateRequest,
    user: UserDependency,
    user_registry: UserRegistryDependency,
) -> MessageResponse:
    """Update an existing secret for the current user."""
    logger.info(f"Updating secret '{secret_name}' for user: {user}")

    try:
        _ensure_secret_exists(user_registry, user, secret_name)
        await user_registry.set_secret(user, secret_name, request.value)

        logger.info(f"Successfully updated secret '{secret_name}' for user: {user}")
        return MessageResponse(message=f"Secret '{secret_name}' updated successfully")

    except HTTPException:
        raise
    except Exception as e:
        _handle_secret_operation_error(e, "update", user, secret_name)


@router.delete("/secrets/{secret_name}", response_model=MessageResponse)
async def delete_secret(
    secret_name: str,
    user: UserDependency,
    user_registry: UserRegistryDependency,
) -> MessageResponse:
    """Delete a secret for the current user."""
    logger.info(f"Deleting secret '{secret_name}' for user: {user}")

    try:
        _ensure_secret_exists(user_registry, user, secret_name)
        await user_registry.delete_secret(user, secret_name)

        logger.info(f"Successfully deleted secret '{secret_name}' for user: {user}")
        return MessageResponse(message=f"Secret '{secret_name}' deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        _handle_secret_operation_error(e, "delete", user, secret_name)
