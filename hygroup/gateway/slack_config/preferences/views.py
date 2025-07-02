from typing import Any, Dict, List, Optional

from hygroup.gateway.slack_config.models import UserPreferencesViewModel


class UserPreferenceViewBuilder:
    @staticmethod
    def build_user_preferences_section(user_id: str, has_preferences: bool) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚙️ User Preferences",
                    "emoji": True,
                },
            },
            {"type": "divider"},
        ]

        if has_preferences:
            # Show overflow menu for existing preferences
            overflow_options = [
                {"text": {"type": "plain_text", "text": "View"}, "value": "config_view_user_preferences"},
                {"text": {"type": "plain_text", "text": "Edit"}, "value": "config_edit_user_preferences"},
            ]

            section_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "View or edit your personal preferences and settings.",
                },
                "accessory": {
                    "type": "overflow",
                    "action_id": "config_user_preferences_overflow",
                    "options": overflow_options,
                },
            }
        else:
            # Show create button for new preferences
            section_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Create your personal preferences and settings.",
                },
                "accessory": {
                    "type": "button",
                    "action_id": "config_user_preferences_create",
                    "text": {"type": "plain_text", "text": "Create"},
                    "style": "primary",
                },
            }

        blocks.append(section_block)
        return blocks

    @staticmethod
    def build_user_preferences_view_modal(
        preferences: Optional[UserPreferencesViewModel] = None,
    ) -> Dict[str, Any]:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Your User Preferences*",
                },
            },
            {"type": "divider"},
        ]

        if preferences and preferences.content:
            # Display preferences content in read-only format
            content = preferences.content
            # For view modal, we can show more content since it's read-only
            if len(content) > 2900:  # Slack has a ~3000 character limit for rich text blocks
                content = content[:2900] + "..."

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
                        "text": "_No preferences available._",
                    },
                }
            )

        return {
            "type": "modal",
            "callback_id": "config_user_preferences_view_modal",
            "title": {"type": "plain_text", "text": "User Preferences"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": blocks,
        }

    @staticmethod
    def build_user_preferences_edit_modal(
        current_preferences: Optional[UserPreferencesViewModel] = None,
    ) -> Dict[str, Any]:
        initial_value = current_preferences.content if current_preferences else ""

        return {
            "type": "modal",
            "callback_id": "config_user_preferences_edited_view",
            "title": {"type": "plain_text", "text": "Edit User Preferences"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Edit your personal preferences:*",
                    },
                },
                {
                    "type": "input",
                    "block_id": "preferences_content",
                    "label": {"type": "plain_text", "text": "Preferences Content"},
                    "element": {
                        "action_id": "content_input",
                        "type": "plain_text_input",
                        "multiline": True,
                        "initial_value": initial_value,
                        "placeholder": {"type": "plain_text", "text": "Enter your preferences here..."},
                    },
                    "hint": {
                        "type": "plain_text",
                        "text": "Use Markdown formatting for better readability",
                    },
                },
            ],
        }
