import logging

from slack_sdk.web.async_client import AsyncWebClient

from hygroup.agent.default.agent import AgentSettings
from hygroup.agent.default.registry import DefaultAgentRegistry
from hygroup.gateway.slack.app_home.agent.validator import AgentValidator
from hygroup.gateway.slack.app_home.agent.views import AgentViewBuilder
from hygroup.gateway.slack.app_home.models import AgentListViewModel, AgentViewModel

logger = logging.getLogger(__name__)


class AgentConfigHandlers:
    def __init__(self, client: AsyncWebClient, agent_registry: DefaultAgentRegistry):
        self._client = client
        self._agent_registry = agent_registry

    async def _get_agents(self) -> list[AgentListViewModel]:
        agents = []
        for agent_name, config in (await self._agent_registry.get_configs()).items():
            agents.append(
                AgentListViewModel(
                    name=agent_name,
                    description=config["description"],
                    emoji=config.get("emoji"),
                )
            )
        return sorted(agents, key=lambda x: x.name)

    async def _get_agent(self, name: str) -> AgentViewModel | None:
        if agent := await self._agent_registry.get_config(name):
            return AgentViewModel.from_agent_config(agent)
        return None

    async def _get_agent_names(self) -> list[str]:
        return list(await self._agent_registry.get_registered_names())

    async def _save_agent(self, agent: AgentViewModel):
        await self._agent_registry.add_config(
            name=agent.name,
            description=agent.description,
            settings=AgentSettings.from_dict(
                {
                    "model": agent.model,
                    "instructions": agent.instructions,
                    "mcp_settings": agent.mcp_settings,
                    "model_settings": agent.model_settings,
                    "tools": agent.tools,
                }
            ),
            handoff=agent.handoff,
            emoji=agent.emoji,
        )

    async def _update_agent(self, agent: AgentViewModel):
        config = await self._agent_registry.get_config(agent.name)
        if config is None:
            logger.warning(f"Agent not found: {agent.name}")
            return

        await self._agent_registry.update_config(
            name=agent.name,
            description=agent.description,
            settings=AgentSettings.from_dict(
                {
                    "model": agent.model,
                    "instructions": agent.instructions,
                    "mcp_settings": agent.mcp_settings,
                    "model_settings": agent.model_settings,
                    "tools": agent.tools,
                }
            ),
            handoff=agent.handoff,
            emoji=agent.emoji,
        )

    async def _delete_agent(self, agent_name: str):
        await self._agent_registry.remove_config(agent_name)

    async def handle_agent_menu(self, ack, body, client):
        await ack()

        selected_option = body["actions"][0]["selected_option"]["value"]
        action, agent_name = selected_option.split(":", 1)

        if action == "view":
            await self._handle_view_agent(body, agent_name)
        elif action == "edit":
            # admin check is done by caller
            await self._handle_edit_agent(body, agent_name)
        elif action == "delete":
            # admin check is done by caller
            await self._handle_delete_agent(body, agent_name)

    async def _handle_view_agent(self, body, agent_name: str):
        agent = await self._get_agent(agent_name)
        if not agent:
            logger.warning(f"Agent not found: {agent_name}")
            return

        modal = AgentViewBuilder.build_agent_view_modal(agent)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_add_agent(self, ack, body, client):
        await ack()

        # admin check is done by caller
        modal = AgentViewBuilder.build_agent_form_modal()
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_agent_added(self, ack, body, client, view, slack_logger):
        # Extract form data
        name = view["state"]["values"]["agent_name"]["name_input"].get("value") or ""
        description = view["state"]["values"]["agent_description"]["description_input"].get("value") or ""
        model_str = view["state"]["values"]["agent_model"]["model_input"].get("value") or ""
        model_settings_str = view["state"]["values"]["agent_model_settings"]["model_settings_input"].get("value") or ""
        instructions = view["state"]["values"]["agent_instructions"]["instructions_input"].get("value") or ""
        mcp_settings_str = view["state"]["values"]["agent_mcp_settings"]["mcp_settings_input"].get("value") or ""
        tools_str = view["state"]["values"]["agent_tools"]["tools_input"].get("value") or ""
        emoji = view["state"]["values"]["agent_emoji"]["emoji_input"].get("value") or ""

        # Extract checkboxes from input block
        selected_options = (
            view["state"]["values"]
            .get("agent_handoff_options", {})
            .get("agent_options", {})
            .get("selected_options", [])
        )
        handoff = any(option["value"] == "handoff" for option in selected_options)

        # Get existing agent names for validation
        existing_names = await self._get_agent_names()

        # Validate all fields
        errors = AgentValidator.validate_agent_data(
            name.strip(),
            description.strip(),
            model_str.strip(),
            instructions.strip(),
            mcp_settings_str.strip(),
            model_settings_str.strip(),
            tools_str.strip(),
            existing_names=existing_names,
        )

        if errors:
            await ack(
                {
                    "response_action": "errors",
                    "errors": errors,
                }
            )
            return

        # Parse validated data
        model_data, _ = AgentValidator.validate_model(model_str.strip())
        mcp_data, _ = AgentValidator.validate_mcp_settings(mcp_settings_str.strip())
        model_settings_data, _ = AgentValidator.validate_model_settings(model_settings_str.strip())
        tools_data, _ = AgentValidator.validate_tools(tools_str.strip())

        # Create agent
        agent = AgentViewModel(
            name=name.strip(),
            description=description.strip(),
            model=model_data,  # type: ignore
            instructions=instructions.strip(),
            mcp_settings=mcp_data or [],
            model_settings=model_settings_data,
            tools=tools_data or [],
            handoff=handoff,
            emoji=emoji.strip(),
        )

        try:
            await self._save_agent(agent)
            await ack()
            logger.info(f"Agent created: {agent.name}")
        except ValueError as e:
            await ack(
                {
                    "response_action": "errors",
                    "errors": {"agent_name": str(e)},
                }
            )

    async def _handle_edit_agent(self, body, agent_name: str):
        agent = await self._get_agent(agent_name)
        if not agent:
            logger.warning(f"Agent not found: {agent_name}")
            return

        modal = AgentViewBuilder.build_agent_form_modal(agent, is_edit=True)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_agent_edited(self, ack, body, client, view, slack_logger):
        agent_name = view["private_metadata"]
        existing_agent = await self._get_agent(agent_name)
        if not existing_agent:
            await ack()
            return

        # Extract form data
        description = view["state"]["values"]["agent_description"]["description_input"].get("value") or ""
        model_str = view["state"]["values"]["agent_model"]["model_input"].get("value") or ""
        model_settings_str = view["state"]["values"]["agent_model_settings"]["model_settings_input"].get("value") or ""
        instructions = view["state"]["values"]["agent_instructions"]["instructions_input"].get("value") or ""
        mcp_settings_str = view["state"]["values"]["agent_mcp_settings"]["mcp_settings_input"].get("value") or ""
        tools_str = view["state"]["values"]["agent_tools"]["tools_input"].get("value") or ""
        emoji = view["state"]["values"]["agent_emoji"]["emoji_input"].get("value") or ""

        # Extract checkboxes from input block
        selected_options = (
            view["state"]["values"]
            .get("agent_handoff_options", {})
            .get("agent_options", {})
            .get("selected_options", [])
        )
        handoff = any(option["value"] == "handoff" for option in selected_options)

        # Validate all fields (excluding name since it can't be changed)
        errors = AgentValidator.validate_agent_data(
            agent_name,  # Use existing name
            description.strip(),
            model_str.strip(),
            instructions.strip(),
            mcp_settings_str.strip(),
            model_settings_str.strip(),
            tools_str.strip(),
            validate_name_field=False,
        )

        if errors:
            await ack(
                {
                    "response_action": "errors",
                    "errors": errors,
                }
            )
            return

        # Parse validated data
        model_data, _ = AgentValidator.validate_model(model_str.strip())
        mcp_data, _ = AgentValidator.validate_mcp_settings(mcp_settings_str.strip())
        model_settings_data, _ = AgentValidator.validate_model_settings(model_settings_str.strip())
        tools_data, _ = AgentValidator.validate_tools(tools_str.strip())

        # Update agent
        updated_agent = AgentViewModel(
            name=agent_name,
            description=description.strip(),
            model=model_data,  # type: ignore
            instructions=instructions.strip(),
            mcp_settings=mcp_data or [],
            model_settings=model_settings_data,
            tools=tools_data or [],
            handoff=handoff,
            emoji=emoji.strip(),
        )

        await self._update_agent(updated_agent)
        await ack()

        logger.info(f"Agent updated: {agent_name}")

    async def _handle_delete_agent(self, body, agent_name: str):
        agent = await self._get_agent(agent_name)
        if not agent:
            logger.warning(f"Agent not found: {agent_name}")
            return

        modal = AgentViewBuilder.build_agent_delete_modal(agent)
        await self._client.views_open(trigger_id=body["trigger_id"], view=modal)

    async def handle_agent_delete_confirmed(self, ack, body, client, view, slack_logger):
        agent_name = view["private_metadata"]

        await self._delete_agent(agent_name)

        logger.info(f"Agent deleted: {agent_name}")

        await ack()
