from typing import Any, Dict, List, Optional

from hygroup.gateway.slack_config.models import ActivationPolicyViewModel


class ActivationPolicyViewBuilder:
    @staticmethod
    def build_activation_policy_section(is_admin: bool) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔄 Activation Policy",
                    "emoji": True,
                },
            },
            {"type": "divider"},
        ]

        # Description section with overflow menu
        overflow_options = [{"text": {"type": "plain_text", "text": "View"}, "value": "config_view_activation_policy"}]

        if is_admin:
            overflow_options.append(
                {"text": {"type": "plain_text", "text": "Edit"}, "value": "config_edit_activation_policy"}
            )

        section_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "View the current system activation policy and guidelines.",
            },
            "accessory": {
                "type": "overflow",
                "action_id": "config_activation_policy_overflow",
                "options": overflow_options,
            },
        }

        blocks.append(section_block)

        return blocks

    @staticmethod
    def build_activation_policy_view_modal(
        policy: Optional[ActivationPolicyViewModel] = None,
    ) -> Dict[str, Any]:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Current System Activation Policy*",
                },
            },
            {"type": "divider"},
        ]

        if policy and policy.content:
            # Display policy content in read-only format
            content = policy.content
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
                        "text": "_No policy available._",
                    },
                }
            )

        return {
            "type": "modal",
            "callback_id": "config_activation_policy_view_modal",
            "title": {"type": "plain_text", "text": "Activation Policy"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": blocks,
        }

    @staticmethod
    def build_activation_policy_edit_modal(
        current_policy: Optional[ActivationPolicyViewModel] = None,
    ) -> Dict[str, Any]:
        return {
            "type": "modal",
            "callback_id": "config_activation_policy_edited_view",
            "title": {"type": "plain_text", "text": "Edit Activation Policy"},
            "submit": {"type": "plain_text", "text": "Save"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Edit the system activation policy:*",
                    },
                },
                {
                    "type": "input",
                    "block_id": "policy_content",
                    "label": {"type": "plain_text", "text": "Policy Content"},
                    "element": {
                        "action_id": "content_input",
                        "type": "plain_text_input",
                        "multiline": True,
                        "initial_value": current_policy.content if current_policy else "",
                        "placeholder": {"type": "plain_text", "text": "Enter the activation policy content here..."},
                    },
                    "hint": {
                        "type": "plain_text",
                        "text": "Use Markdown formatting for better readability",
                    },
                },
            ],
        }
