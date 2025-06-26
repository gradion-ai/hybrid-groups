from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """Response model for user information."""

    username: str = Field(..., description="Username of the authenticated user")


class SecretResponse(BaseModel):
    """Response model for secret information."""

    name: str = Field(..., description="Name of the secret")
    created_at: Optional[datetime] = Field(None, description="When the secret was created")


class SecretValueResponse(BaseModel):
    """Response model for secret value retrieval."""

    name: str = Field(..., description="Name of the secret")
    value: str = Field(..., description="Value of the secret")


class SecretsListResponse(BaseModel):
    """Response model for list of secrets."""

    secrets: List[SecretResponse] = Field(..., description="List of user secrets")


class SecretCreateRequest(BaseModel):
    """Request model for creating a new secret."""

    name: str = Field(..., min_length=1, description="Name of the secret")
    value: str = Field(..., min_length=1, description="Value of the secret")


class SecretUpdateRequest(BaseModel):
    """Request model for updating an existing secret."""

    value: str = Field(..., min_length=1, description="New value for the secret")


class MappingResponse(BaseModel):
    """Response model for mapping information."""

    gateway_name: str = Field(..., description="Name of the gateway (e.g., 'slack', 'github')")
    gateway_username: str = Field(..., description="Username on the gateway")


class MappingsListResponse(BaseModel):
    """Response model for list of mappings."""

    mappings: List[MappingResponse] = Field(..., description="List of user mappings")


class MessageResponse(BaseModel):
    """Response model for operation messages."""

    message: str = Field(..., description="Operation result message")
