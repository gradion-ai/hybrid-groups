import os
import secrets
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

from hygroup import PROJECT_ROOT_PATH

# Default CORS origins for local environment
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


class ApiServerSettings(BaseSettings):
    api_port: int = 8000

    cors_origins: str = DEFAULT_CORS_ORIGINS

    ## Logging
    log_level: str = "INFO"
    log_config_path: str = str((PROJECT_ROOT_PATH.parent / "logging.yaml").absolute())

    ## JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT_PATH.parent / ".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )

    __hash__ = object.__hash__

    def __init__(self, **kwargs):
        self._generate_jwt_secret_if_not_exists()
        super().__init__(**kwargs)

    def _generate_jwt_secret_if_not_exists(self):
        env_file = PROJECT_ROOT_PATH.parent / ".env"

        if os.getenv("JWT_SECRET_KEY") or (env_file.exists() and "JWT_SECRET_KEY=" in env_file.read_text()):
            return

        secret_key = secrets.token_urlsafe(64)
        with open(env_file, "a") as f:
            f.write(f"\nJWT_SECRET_KEY={secret_key}\n")

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
