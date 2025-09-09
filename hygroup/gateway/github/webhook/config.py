from pathlib import Path

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    webhook_port: int = 8000
    webhook_secret: str

    log_level: str = "INFO"
    log_config_path: str = str((Path(__file__).parent / "logging.yaml").absolute())
