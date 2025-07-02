from typing import Any, Dict, List


class SecretViewBuilder:
    @staticmethod
    def build_user_secrets_section(secrets: Dict[str, str]) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔑 User Secrets",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Manage your user secrets.",
                },
                "accessory": {
                    "type": "button",
                    "action_id": "config_add_user_secret",
                    "text": {"type": "plain_text", "text": "Add User Secret"},
                    "style": "primary",
                },
            },
        ]

        if secrets:
            for key in secrets:
                blocks.append(SecretViewBuilder.build_secret_item(key, "config_user_secret_var_menu"))
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No user secrets configured yet._",
                    },
                }
            )

        return blocks

    @staticmethod
    def build_global_secrets_section(secrets: Dict[str, str]) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🌐 Global Secrets",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Manage global secrets shared across all users.",
                },
                "accessory": {
                    "type": "button",
                    "action_id": "config_add_global_secret",
                    "text": {"type": "plain_text", "text": "Add Global Secret"},
                    "style": "primary",
                },
            },
        ]

        if secrets:
            for key in secrets:
                blocks.append(SecretViewBuilder.build_secret_item(key, "config_global_secret_var_menu"))
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No global secrets configured yet._",
                    },
                }
            )

        return blocks

    @staticmethod
    def build_secret_item(key: str, action_id_prefix: str) -> Dict[str, Any]:
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{key}*\n`•••••`",
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
    def build_add_secret_modal(is_global: bool = False) -> Dict[str, Any]:
        title = "Add Global Secret" if is_global else "Add Secret"
        callback_id = "config_global_secret_added_view" if is_global else "config_user_secret_added_view"
        key_block_id = "global_secret_key" if is_global else "env_key"
        value_block_id = "global_secret_value" if is_global else "env_value"

        return {
            "type": "modal",
            "callback_id": callback_id,
            "title": {"type": "plain_text", "text": title},
            "submit": {"type": "plain_text", "text": "Add"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": key_block_id,
                    "label": {"type": "plain_text", "text": "Secret Name"},
                    "element": {
                        "action_id": "key_input",
                        "type": "plain_text_input",
                        "placeholder": {"type": "plain_text", "text": "e.g., API_KEY"},
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
    def build_edit_secret_modal(key: str, is_global: bool = False) -> Dict[str, Any]:
        title = "Edit Global Secret" if is_global else "Edit Secret"
        callback_id = "config_global_secret_edited_view" if is_global else "config_user_secret_edited_view"
        value_block_id = "global_secret_value" if is_global else "env_value"

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
                        "text": f"*{'Global Secret' if is_global else 'Secret'} Name:* `{key}`",
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
    def build_delete_secret_modal(key: str, user_id: str, is_global: bool = False) -> Dict[str, Any]:
        title = "Delete Global Secret" if is_global else "Delete Secret"
        callback_id = (
            "config_global_secret_delete_confirm_view" if is_global else "config_user_secret_delete_confirm_view"
        )
        warning = (
            "This action cannot be undone and will affect all users." if is_global else "This action cannot be undone."
        )

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
                        "text": f"❌ *Are you sure you want to delete the {'global ' if is_global else ''}secret `{key}`?*\n\n{warning}",
                    },
                }
            ],
        }
