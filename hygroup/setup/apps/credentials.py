import stat
from pathlib import Path
from typing import Optional, Tuple

from hygroup.setup.apps.models import GitHubAppCredentials


class CredentialManager:
    def __init__(self, key_folder: Path, env_file: Path):
        self.key_folder = key_folder
        self.env_file = env_file

    async def save_github_credentials(
        self, credentials: GitHubAppCredentials, organization: str | None, webhook_url: str | None = None
    ) -> Tuple[Path, Path]:
        key_path = await self._save_private_key(credentials)
        await self._set_github_env_variables(credentials, key_path, organization, webhook_url)
        return key_path, self.env_file

    async def _save_private_key(self, credentials: GitHubAppCredentials) -> Path:
        key_filename = f"{credentials.slug}-{credentials.app_id}.pem"
        key_path = self.key_folder / key_filename

        key_path.write_text(credentials.pem)
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

        return key_path

    async def _set_github_env_variables(
        self,
        credentials: GitHubAppCredentials,
        key_path: Path,
        organization: Optional[str],
        webhook_url: Optional[str] = None,
    ) -> None:
        org_info = f"Organization: {organization}" if organization else "Personal Account"

        webhook_line = f"GITHUB_APP_WEBHOOK_URL={webhook_url}\n" if webhook_url else ""

        env_content = f"""
# GitHub App: {credentials.slug} ({org_info})
GITHUB_APP_ID={credentials.app_id}
GITHUB_APP_USERNAME={credentials.slug}
GITHUB_APP_CLIENT_SECRET={credentials.client_secret}
GITHUB_APP_WEBHOOK_SECRET={credentials.webhook_secret}
GITHUB_APP_PRIVATE_KEY_PATH={key_path}
{webhook_line}"""

        with open(self.env_file, "a") as f:
            f.write(env_content)

    def append_github_installation_id(self, installation_id: str) -> None:
        env_line = f"GITHUB_APP_INSTALLATION_ID={installation_id}\n"

        with open(self.env_file, "a") as f:
            f.write(env_line)

    async def save_slack_credentials(self, app_name: str, bot_token: str, app_token: str, app_id: str) -> Path:
        env_content = f"""
# Slack App: {app_name}
SLACK_BOT_TOKEN={bot_token}
SLACK_APP_TOKEN={app_token}
SLACK_APP_ID={app_id}
"""
        with open(self.env_file, "a") as f:
            f.write(env_content)

        return self.env_file
