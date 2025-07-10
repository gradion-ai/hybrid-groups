import json
from typing import Any

from hygroup.gateway.slack.app_home.models import AgentListViewModel, AgentViewModel


class AgentViewBuilder:
    @staticmethod
    def build_agents_section(agents: list[AgentListViewModel], is_system_editor: bool) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [
            {"type": "section", "text": {"type": "plain_text", "text": " "}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Agents*",
                },
            },
            {"type": "divider"},
        ]

        description_text = "Available agents and their configuration."

        if is_system_editor:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": description_text,
                    },
                    "accessory": {
                        "type": "button",
                        "action_id": "home_add_agent",
                        "text": {"type": "plain_text", "text": "Add Agent"},
                        "style": "primary",
                    },
                }
            )
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": description_text,
                    },
                }
            )

        blocks.extend(
            [
                {"type": "section", "text": {"type": "plain_text", "text": " "}},
            ]
        )

        if agents:
            for agent in agents:
                blocks.append(AgentViewBuilder.build_agent_item(agent, is_system_editor))
        else:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No agents configured yet._",
                    },
                }
            )

        return blocks

    @staticmethod
    def build_agent_item(agent: AgentListViewModel, is_system_editor: bool) -> dict[str, Any]:
        overflow_options = [
            {
                "text": {"type": "plain_text", "text": "View"},
                "value": f"view:{agent.name}",
            }
        ]

        if is_system_editor:
            overflow_options.extend(
                [
                    {
                        "text": {"type": "plain_text", "text": "Edit"},
                        "value": f"edit:{agent.name}",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Delete"},
                        "value": f"delete:{agent.name}",
                    },
                ]
            )

        emoji_text = ""
        if agent.emoji:
            emoji_text = f":{agent.emoji}: "

        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji_text}*{agent.name}*\n{agent.description}",
            },
            "accessory": {
                "type": "overflow",
                "action_id": f"home_agent_menu:{agent.name}",
                "options": overflow_options,
            },
        }

    @staticmethod
    def build_agent_view_modal(agent: AgentViewModel) -> dict[str, Any]:
        try:
            model_formatted = json.dumps(agent.model, indent=2)
        except (json.JSONDecodeError, TypeError):
            model_formatted = str(agent.model)

        mcp_settings_formatted = json.dumps(agent.mcp_settings, indent=2)
        model_settings_formatted = json.dumps(agent.model_settings or {}, indent=2)
        tools_formatted = json.dumps(agent.tools, indent=2)

        emoji_text = ""
        if agent.emoji:
            emoji_text = f":{agent.emoji}: "

        return {
            "type": "modal",
            "title": {"type": "plain_text", "text": "Agent Details"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji_text}*{agent.name}*",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Description:*\n```{agent.description}```",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*System Instructions:*\n```{agent.instructions}```",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Model:*\n```\n{model_formatted}\n```",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Model Settings:*\n```\n{model_settings_formatted}\n```",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*MCP Settings:*\n```\n{mcp_settings_formatted}\n```",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Python Coroutines:*\n```\n{tools_formatted}\n```",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Handoff:*\n{'☑️' if agent.handoff else '☐'} Enable Handoff",
                    },
                },
            ],
        }

    @staticmethod
    def build_agent_form_modal(agent: AgentViewModel | None = None, is_edit: bool = False) -> dict[str, Any]:
        title = "Edit Agent" if is_edit else "Add Agent"
        callback_id = "home_agent_edited_view" if is_edit else "home_agent_added_view"

        blocks = []

        if is_edit and agent:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Agent Name:* `{agent.name}`",
                    },
                }
            )
        else:
            blocks.append(
                {
                    "type": "input",
                    "block_id": "agent_name",
                    "label": {"type": "plain_text", "text": "Name"},
                    "element": {
                        "action_id": "name_input",
                        "type": "plain_text_input",
                        "placeholder": {"type": "plain_text", "text": "e.g. custom-agent"},
                    },
                    "hint": {"type": "plain_text", "text": "Agent name must be unique and cannot be changed later"},
                }
            )

        description_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_description",
            "label": {"type": "plain_text", "text": "Description"},
            "element": {
                "action_id": "description_input",
                "type": "plain_text_input",
                "multiline": True,
                "initial_value": agent.description if agent and is_edit else "",
                "placeholder": {"type": "plain_text", "text": "Describe what the agent does."},
            },
            "hint": {
                "type": "plain_text",
                "text": "Will be used by background reasoning for selecting and activating the agent.",
            },
        }

        model_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_model",
            "label": {"type": "plain_text", "text": "Model"},
            "element": {
                "action_id": "model_input",
                "type": "plain_text_input",
                "multiline": True,
                "initial_value": json.dumps(agent.model)
                if agent and is_edit and isinstance(agent.model, dict)
                else str(agent.model)
                if agent and is_edit
                else "",
                "placeholder": {
                    "type": "plain_text",
                    "text": 'e.g. "gemini-2.5-flash"',
                },
            },
            "hint": {
                "type": "plain_text",
                "text": "PydanticAI model name (see https://ai.pydantic.dev/api/models/base/)",
            },
        }

        model_settings_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_model_settings",
            "label": {"type": "plain_text", "text": "Model Settings"},
            "optional": True,
            "element": {
                "action_id": "model_settings_input",
                "type": "plain_text_input",
                "multiline": True,
                "initial_value": json.dumps(agent.model_settings) if agent and is_edit and agent.model_settings else "",
                "placeholder": {
                    "type": "plain_text",
                    "text": '{\n  "google_thinking_config": {\n    "include_thoughts": true\n  }\n}',
                },
            },
            "hint": {
                "type": "plain_text",
                "text": "PydanticAI model settings. BaseSettings (https://ai.pydantic.dev/api/settings/) has common options. Model-specific settings in model docs (e.g. https://ai.pydantic.dev/models/google/#model-settings).",
            },
        }

        instructions_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_instructions",
            "label": {"type": "plain_text", "text": "System instructions"},
            "element": {
                "action_id": "instructions_input",
                "type": "plain_text_input",
                "multiline": True,
                "initial_value": agent.instructions if agent and is_edit else "",
                "placeholder": {"type": "plain_text", "text": "System instructions for the agent."},
            },
        }

        mcp_settings_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_mcp_settings",
            "label": {"type": "plain_text", "text": "MCP Settings"},
            "optional": True,
            "element": {
                "action_id": "mcp_settings_input",
                "type": "plain_text_input",
                "multiline": True,
                "initial_value": json.dumps(agent.mcp_settings) if agent and is_edit and agent.mcp_settings else "",
                "placeholder": {
                    "type": "plain_text",
                    "text": '[{\n  "server_config": {\n    "command": "...",  \n    "args": [...], \n    "env": { "API_KEY": "${API_KEY}" } \n  },\n  "session_scope": false\n}]',
                },
            },
            "hint": {
                "type": "plain_text",
                "text": "JSON array of MCP server configurations. Supports variable substitution for registered secrets and environment variables.",
            },
        }

        tools_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_tools",
            "label": {"type": "plain_text", "text": "Python Coroutines"},
            "optional": True,
            "element": {
                "action_id": "tools_input",
                "type": "plain_text_input",
                "multiline": True,
                "initial_value": json.dumps(agent.tools) if agent and is_edit and agent.tools else "",
                "placeholder": {
                    "type": "plain_text",
                    "text": '[{\n  "module": "examples.app_server",\n  "function": "get_user_preferences"\n}]',
                },
            },
            "hint": {
                "type": "plain_text",
                "text": "JSON array of Python coroutines to import as tools. Each tool definition must have 'module' and 'function' fields.",
            },
        }

        emoji_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_emoji",
            "label": {"type": "plain_text", "text": "Emoji"},
            "element": {
                "action_id": "emoji_input",
                "type": "plain_text_input",
                "initial_value": agent.emoji if agent and agent.emoji and is_edit else "",
                "placeholder": {"type": "plain_text", "text": "robot_face"},
            },
            "hint": {"type": "plain_text", "text": "Slack emoji code without colons."},
        }

        blocks.extend(
            [
                emoji_block,
                description_block,
                instructions_block,
                model_block,
                model_settings_block,
                mcp_settings_block,
                tools_block,
            ]
        )

        # Build checkbox options
        options = [
            {
                "text": {"type": "plain_text", "text": "Enable Handoff"},
                "value": "handoff",
                "description": {
                    "type": "mrkdwn",
                    "text": "Allow agent to hand off to other agents",
                },
            }
        ]

        # Pre-select checkboxes for edit mode
        initial_options = []
        if agent and is_edit:
            if agent.handoff:
                initial_options.append(options[0])

        checkbox_element: dict[str, Any] = {
            "type": "checkboxes",
            "action_id": "agent_options",
            "options": options,
        }
        if initial_options:
            checkbox_element["initial_options"] = initial_options

        # Use input block instead of actions block for form behavior
        checkbox_input_block: dict[str, Any] = {
            "type": "input",
            "block_id": "agent_handoff_options",
            "label": {"type": "plain_text", "text": "Handoff"},
            "optional": True,
            "element": checkbox_element,
        }
        blocks.append(checkbox_input_block)

        modal = {
            "type": "modal",
            "callback_id": callback_id,
            "title": {"type": "plain_text", "text": title},
            "submit": {"type": "plain_text", "text": "Save" if is_edit else "Add"},
            "blocks": blocks,
        }

        if is_edit and agent:
            modal["private_metadata"] = agent.name

        return modal

    @staticmethod
    def build_agent_delete_modal(agent: AgentViewModel) -> dict[str, Any]:
        return {
            "type": "modal",
            "callback_id": "home_agent_delete_confirm_view",
            "title": {"type": "plain_text", "text": "Delete Agent"},
            "submit": {"type": "plain_text", "text": "Delete"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": agent.name,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *Are you sure you want to delete the agent `{agent.name}`?*\n\nThis action cannot be undone!",
                    },
                }
            ],
        }
