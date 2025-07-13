from typing import Any


class UserPreferenceViewBuilder:
    @staticmethod
    def build_user_preferences_section(preferences: str | None) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Preferences*",
                },
            },
            {"type": "divider"},
        ]

        description_text = "Personalize behavior and responses you receive from agents."

        if preferences:
            overflow_options = [
                {"text": {"type": "plain_text", "text": "Edit"}, "value": "home_edit_user_preferences"},
                {"text": {"type": "plain_text", "text": "Delete"}, "value": "home_delete_user_preferences"},
            ]

            section_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": description_text,
                },
                "accessory": {
                    "type": "overflow",
                    "action_id": "home_user_preferences_overflow",
                    "options": overflow_options,
                },
            }
        else:
            section_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": description_text,
                },
                "accessory": {
                    "type": "button",
                    "action_id": "home_user_preferences_create",
                    "text": {"type": "plain_text", "text": "Set Preferences"},
                    "style": "primary",
                },
            }

        blocks.append(section_block)
        blocks.append({"type": "section", "text": {"type": "plain_text", "text": " "}})

        if preferences:
            content = preferences
            if len(content) > 3000:  # Slack has a 3000 character limit for text blocks
                content = content[:2997] + "..."

            blocks.append(
                {
                    "type": "rich_text",
                    "elements": [
                        {
                            "type": "rich_text_preformatted",
                            "elements": [
                                {
                                    "type": "text",
                                    "text": content,
                                }
                            ],
                        }
                    ],
                }
            )
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No preferences set_",
                    },
                }
            )

        return blocks

    @staticmethod
    def build_user_preferences_edit_modal(
        current_preferences: str | None = None,
    ) -> dict[str, Any]:
        initial_value = current_preferences if current_preferences else ""

        return {
            "type": "modal",
            "callback_id": "home_user_preferences_edited_view",
            "title": {"type": "plain_text", "text": "Edit Preferences"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "preferences_content",
                    "label": {"type": "plain_text", "text": "Your Preferences:"},
                    "element": {
                        "action_id": "content_input",
                        "type": "plain_text_input",
                        "multiline": True,
                        "initial_value": initial_value,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "E.g.: \n* Always use concise answers\n* I always want to see emojis",
                        },
                    },
                    "hint": {
                        "type": "plain_text",
                        "text": "Supports Markdown formatting.",
                    },
                },
            ],
        }

    @staticmethod
    def build_user_preferences_delete_modal() -> dict[str, Any]:
        return {
            "type": "modal",
            "callback_id": "home_user_preferences_delete_confirm_view",
            "title": {"type": "plain_text", "text": "Delete Preferences"},
            "submit": {"type": "plain_text", "text": "Delete"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "❌ *Are you sure you want to delete your preferences?*\n\nThis action cannot be undone!",
                    },
                }
            ],
        }
