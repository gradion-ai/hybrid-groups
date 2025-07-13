from typing import Any


class SecretViewBuilder:
    @staticmethod
    def build_user_secrets_section(secrets: dict[str, str]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Secrets*",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Agents use your secrets when running MCP servers *on your behalf*. Secrets are encrypted and never shared with other users.",
                },
                "accessory": {
                    "type": "button",
                    "action_id": "home_add_user_secret",
                    "text": {"type": "plain_text", "text": "Add Secret"},
                    "style": "primary",
                },
            },
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
        ]

        if secrets:
            for key in secrets:
                blocks.append(SecretViewBuilder.build_secret_item(key, "home_user_secret_var_menu"))
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No secrets configured_",
                    },
                }
            )

        return blocks

    @staticmethod
    def build_secret_item(key: str, action_id_prefix: str) -> dict[str, Any]:
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{key}*   `•••••`",
            },
            "accessory": {
                "type": "overflow",
                "action_id": f"{action_id_prefix}:{key}",
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Edit"},
                        "value": f"edit:{key}",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Delete"},
                        "value": f"delete:{key}",
                    },
                ],
            },
        }

    @staticmethod
    def build_add_secret_modal() -> dict[str, Any]:
        title = "Add Secret"
        callback_id = "home_user_secret_added_view"
        key_block_id = "user_secret_key"
        value_block_id = "user_secret_value"

        return {
            "type": "modal",
            "callback_id": callback_id,
            "title": {"type": "plain_text", "text": title},
            "submit": {"type": "plain_text", "text": "Add"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": key_block_id,
                    "label": {"type": "plain_text", "text": "Name"},
                    "element": {
                        "action_id": "key_input",
                        "type": "plain_text_input",
                        "placeholder": {"type": "plain_text", "text": "e.g. API_KEY"},
                    },
                    "hint": {"type": "plain_text", "text": "Use uppercase letters, numbers, and underscores only"},
                },
                {
                    "type": "input",
                    "block_id": value_block_id,
                    "label": {"type": "plain_text", "text": "Value"},
                    "element": {
                        "action_id": "value_input",
                        "type": "plain_text_input",
                        "placeholder": {"type": "plain_text", "text": "Enter the secret value"},
                    },
                },
            ],
        }

    @staticmethod
    def build_edit_secret_modal(key: str) -> dict[str, Any]:
        title = "Edit Secret"
        callback_id = "home_user_secret_edited_view"
        value_block_id = "user_secret_value"

        return {
            "type": "modal",
            "callback_id": callback_id,
            "title": {"type": "plain_text", "text": title},
            "submit": {"type": "plain_text", "text": "Save"},
            "private_metadata": key,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Name:* `{key}`",
                    },
                },
                {
                    "type": "input",
                    "block_id": value_block_id,
                    "label": {"type": "plain_text", "text": "New Value"},
                    "element": {
                        "action_id": "value_input",
                        "type": "plain_text_input",
                        "placeholder": {"type": "plain_text", "text": "Enter the new secret value"},
                    },
                },
            ],
        }

    @staticmethod
    def build_delete_secret_modal(key: str, user_id: str) -> dict[str, Any]:
        title = "Delete Secret"
        callback_id = "home_user_secret_delete_confirm_view"

        return {
            "type": "modal",
            "callback_id": callback_id,
            "title": {"type": "plain_text", "text": title},
            "submit": {"type": "plain_text", "text": "Delete"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": f"{user_id}:{key}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *Are you sure you want to delete the secret `{key}`?*\n\nThis action cannot be undone!",
                    },
                }
            ],
        }
