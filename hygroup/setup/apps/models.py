from typing import Any, Dict, List

from pydantic import BaseModel


class GitHubAppCreateRequest(BaseModel):
    app_name: str
    organization: str | None = None


class GitHubAppManifest(BaseModel):
    name: str
    url: str
    hook_attributes: Dict[str, Any]
    redirect_url: str
    default_permissions: Dict[str, str]
    default_events: List[str]
    public: bool = True


class GitHubAppCredentials(BaseModel):
    app_id: int
    slug: str
    name: str
    client_secret: str
    webhook_secret: str
    pem: str
    installation_id: int | None = None


class GitHubManifestResponse(BaseModel):
    manifest: Dict[str, Any]
    github_url: str


class GitHubCompleteRequest(BaseModel):
    installation_id: str | None = None


class GitHubCompleteResponse(BaseModel):
    success: bool
    installation_id_saved: bool


class SlackAppCreateRequest(BaseModel):
    app_name: str
    config_token: str


class SlackAppCreateResponse(BaseModel):
    success: bool
    app_id: str | None = None
    app_name: str | None = None
    error: str | None = None


class SlackCompleteRequest(BaseModel):
    app_id: str
    app_name: str
    app_token: str
    bot_token: str


class SlackCompleteResponse(BaseModel):
    success: bool
    app_user_id: str | None = None
    error: str | None = None
