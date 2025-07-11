import json
from typing import Any, Dict, Tuple

import aiohttp

HYBRID_GROUPS_APP_NAME = "Hybrid Groups"

MANIFEST_TEMPLATE: Dict[str, Any] = {
    "display_information": {"name": ""},
    "features": {
        "app_home": {
            "home_tab_enabled": True,
            "messages_tab_enabled": False,
            "messages_tab_read_only_enabled": False,
        },
        "bot_user": {"display_name": "", "always_online": False},
    },
    "oauth_config": {
        "scopes": {
            "bot": [
                "app_mentions:read",
                "assistant:write",
                "channels:history",
                "groups:history",
                "groups:read",
                "im:history",
                "mpim:history",
                "chat:write",
                "chat:write.customize",
                "channels:read",
                "reactions:write",
                "users:read",
            ]
        }
    },
    "settings": {
        "event_subscriptions": {
            "bot_events": [
                "app_home_opened",
                "app_mention",
                "message.channels",
                "message.groups",
                "message.im",
                "message.mpim",
            ]
        },
        "interactivity": {"is_enabled": True},
        "org_deploy_enabled": False,
        "socket_mode_enabled": True,
        "token_rotation_enabled": False,
    },
}

SLACK_MANIFEST_CREATE_URL = "https://slack.com/api/apps.manifest.create"
SLACK_AUTH_TEST_URL = "https://slack.com/api/auth.test"


class SlackAppSetupService:
    async def create_manifest(self, app_name: str) -> Dict[str, Any]:
        app_name = HYBRID_GROUPS_APP_NAME
        manifest = dict(MANIFEST_TEMPLATE)
        manifest["display_information"]["name"] = app_name
        manifest["features"]["bot_user"]["display_name"] = app_name
        return manifest

    async def create_slack_app(self, manifest: Dict[str, Any], token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        manifest_json = json.dumps(manifest)
        payload = {"manifest": manifest_json}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(SLACK_MANIFEST_CREATE_URL, headers=headers, json=payload) as response:
                    return await response.json()
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Network error: {e}")

    async def get_app_user_id(self, bot_token: str) -> Tuple[bool, str | None, Dict[str, Any]]:
        headers = {"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(SLACK_AUTH_TEST_URL, headers=headers) as response:
                    data = await response.json()

                    if data.get("ok"):
                        return True, data.get("user_id"), data
                    else:
                        return False, None, data

            except aiohttp.ClientError as e:
                return False, None, {"error": f"Network error: {str(e)}"}
