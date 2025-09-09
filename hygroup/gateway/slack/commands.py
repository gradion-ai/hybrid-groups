import html
from typing import Any

from markdown_to_mrkdwn import SlackMarkdownConverter

from hygroup.connect.composio import ComposioConnector
from hygroup.gateway.slack.context import SlackContext


class SlackCommandHandler:
    def __init__(self, context: SlackContext, composio_connector: ComposioConnector):
        self.context = context
        self.composio_connector = composio_connector
        self.converter = SlackMarkdownConverter()

        # Register command handlers with the Slack app.
        self.context.app.command("/hygroup-connect")(self.handle_connect)
        self.context.app.command("/hygroup-command")(self.handle_command)
        self.context.app.command("/hygroup-agents")(self.handle_agents)

    async def handle_connect(self, ack, body, respond):
        await ack()

        user = self.context.resolve_system_user_id(body["user_id"])
        text = body["text"].strip()

        if text:
            block = await self._connect_toolkit(system_user_id=user, toolkit_name=text)
        else:
            block = await self._connection_status(system_user_id=user)

        await respond(blocks=[block])

    async def _connect_toolkit(self, system_user_id: str, toolkit_name: str) -> dict[str, Any]:
        composio_config = await self.composio_connector.load_config()
        toolkit_names = composio_config.toolkit_names()

        if toolkit_name not in toolkit_names:
            toolkits_text = "\n".join(f"- `{toolkit_name}`" for toolkit_name in toolkit_names)
            response_text = f"Invalid toolkit name: `{toolkit_name}`. Must be one of:\n\n{toolkits_text}"
        else:
            redirect_url = await self.composio_connector.connect_toolkit(system_user_id, toolkit_name)
            response_text = f"Follow [this link]({redirect_url}) for authorizing Composio to access your {composio_config.display_name(toolkit_name)} account."

        return {"type": "section", "text": {"type": "mrkdwn", "text": self.converter.convert(response_text)}}

    async def _connection_status(self, system_user_id: str) -> dict[str, Any]:
        composio_config = await self.composio_connector.load_config()
        composio_connections = await self.composio_connector.connection_status(system_user_id, composio_config)

        connection_lines = []

        connected_emoji = ":white_check_mark:"
        disconnected_emoji = ":heavy_multiplication_x:"

        for toolkit_name, connected in sorted(composio_connections.items()):
            emoji = connected_emoji if connected else disconnected_emoji
            connection_lines.append(f"{emoji} `{toolkit_name}` - {composio_config.display_name(toolkit_name)}")

        connections_text = "\n".join(connection_lines) if connection_lines else "No toolkits configured"
        response_text = f"**Composio toolkits** - {connected_emoji} connected {disconnected_emoji} disconnected\n\n{connections_text}"

        return {"type": "section", "text": {"type": "mrkdwn", "text": self.converter.convert(response_text)}}

    async def handle_command(self, ack, body, respond):
        await ack()

        user = self.context.resolve_system_user_id(body["user_id"])
        text = body["text"].strip()

        try:
            response_text = await self._handle_command(text, user)
        except KeyError:
            response_text = ":x: Command not found."
        except ValueError as e:
            response_text = f":x: Error: {str(e)}"
        except Exception as e:
            response_text = f":x: An error occurred: {str(e)}"

        block = {"type": "section", "text": {"type": "mrkdwn", "text": self.converter.convert(response_text)}}
        await respond(blocks=[block])

    async def _handle_command(self, text: str, user: str) -> str:
        command_store = self.context.session_manager.command_store

        if not text or text == "list":
            command_names = await command_store.command_names(user)
            if command_names:
                command_list = "\n".join(f"• `{name}`" for name in sorted(command_names))
                response_text = f"**Saved commands:**\n{command_list}"
            else:
                response_text = "No saved commands found."
        elif text.startswith("save "):
            parts = text[5:].split(None, 1)
            if len(parts) < 2:
                response_text = ":x: Error: Please provide both a command name and command content."
            else:
                command_name, command_content = parts
                command_content = command_content.strip()
                await command_store.save_command(html.unescape(command_content), command_name, user)
                response_text = f":white_check_mark: Command `{command_name}` saved successfully."
        elif text.startswith("view "):
            command_name = text[5:].strip()
            if not command_name:
                response_text = ":x: Error: Please provide a command name."
            else:
                command_content = await command_store.load_command(command_name, user)
                response_text = f"**Command `{command_name}`:**\n```\n{command_content}\n```"
        elif text.startswith("delete "):
            command_name = text[7:].strip()
            if not command_name:
                response_text = ":x: Error: Please provide a command name."
            else:
                await command_store.delete_command(command_name, user)
                response_text = f":white_check_mark: Command `{command_name}` deleted successfully."
        elif text == "help":
            lines = [
                "**Usage:**",
                "- `/hygroup-command` or `/hygroup-command list` - List all saved commands",
                "- `/hygroup-command save <name> <command>` - Save a command",
                "- `/hygroup-command view <name>` - View a command",
                "- `/hygroup-command delete <name>` - Delete a command",
                "- `/hygroup-command help` - Show this help message",
            ]
            response_text = "\n".join(lines)
        else:
            response_text = ":x: Unknown operation. Use `/hygroup-command` without arguments to see usage."

        return response_text

    async def handle_agents(self, ack, body, respond):
        await ack()

        channel_name = body.get("channel_name")

        registry = self.context.session_manager.agent_registries.get_registry(name=channel_name)

        descriptions = registry.get_descriptions()

        agent_lines = []
        for name, description in sorted(descriptions.items()):
            emoji = registry.get_emoji(name)
            emoji_str = f":{emoji}:" if emoji else ":robot_face:"
            agent_lines.append(f"- {emoji_str} `{name}`: {description}")

        if agent_lines:
            agents_text = "\n".join(agent_lines)
            response_text = f"**Available agents**\n\n{agents_text}"
        else:
            response_text = "No agents are currently registered."

        block = {"type": "section", "text": {"type": "mrkdwn", "text": self.converter.convert(response_text)}}
        await respond(blocks=[block])
