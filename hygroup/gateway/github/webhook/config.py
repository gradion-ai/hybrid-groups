from pydantic_settings import BaseSettings, SettingsConfigDict

from hygroup import PROJECT_ROOT_PATH


class AppSettings(BaseSettings):
    api_port: int = 8000

    github_app_webhook_secret: str

    ## Logging
    log_level: str = "INFO"
    log_config_path: str = str((PROJECT_ROOT_PATH.parent / "logging.yaml").absolute())

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT_PATH.parent / ".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )

    __hash__ = object.__hash__
