from typing import Any


class ActivationPolicyViewBuilder:
    @staticmethod
    def build_activation_policy_section(is_system_editor: bool) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Agent Activation Policy*",
                },
            },
            {"type": "divider"},
        ]

        overflow_options = [{"text": {"type": "plain_text", "text": "View"}, "value": "home_view_activation_policy"}]

        if is_system_editor:
            overflow_options.append(
                {"text": {"type": "plain_text", "text": "Edit"}, "value": "home_edit_activation_policy"}
            )

        section_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Defines criteria for automatically activating agents in conversations.",
            },
            "accessory": {
                "type": "overflow",
                "action_id": "home_activation_policy_overflow",
                "options": overflow_options,
            },
        }

        blocks.append(section_block)

        return blocks

    @staticmethod
    def build_activation_policy_view_modal(
        policy: str | None = None,
    ) -> dict[str, Any]:
        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Activation Policy:*",
                },
            },
        ]

        if policy:
            content = policy
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
                        "text": "_No policy available._",
                    },
                }
            )

        return {
            "type": "modal",
            "callback_id": "home_activation_policy_view_modal",
            "title": {"type": "plain_text", "text": "View Activation Policy"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": blocks,
        }

    @staticmethod
    def build_activation_policy_edit_modal(
        current_policy: str | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "modal",
            "callback_id": "home_activation_policy_edited_view",
            "title": {"type": "plain_text", "text": "Edit Activation Policy"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "policy_content",
                    "label": {"type": "plain_text", "text": "Activation Policy:"},
                    "element": {
                        "action_id": "content_input",
                        "type": "plain_text_input",
                        "multiline": True,
                        "initial_value": current_policy if current_policy else "",
                        "placeholder": {"type": "plain_text", "text": "Enter the activation policy..."},
                    },
                    "hint": {
                        "type": "plain_text",
                        "text": "Supports Markdown formatting.",
                    },
                },
            ],
        }
