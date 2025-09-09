# Agent registry

Currently, agents are configured and registered programmatically in *Hybrid Groups*. An agent configuration includes system instructions, model settings, MCP servers and other tools. 

!!! Example

    See [agents.py](https://github.com/gradion-ai/hybrid-groups/blob/main/hygroup/examples/agents.py) for agent configuration and registration, and the [tutorial](tutorial.md) for usage examples.

A common setup is to have a [system agent](#system-agent) and zero or more specialized agents. The system agent can use other agents in the registry as subagents, and selects them based on their `description`. 


## System agent

A system agent monitors all messages in a [group session](tutorial.md#group-sessions). It may decide to stay silent or respond to a message, depending on message content, context and system instructions. [Default instructions](https://github.com/gradion-ai/hybrid-groups/blob/main/hygroup/agent/system/prompt.md) for a system agent can be loaded with `system_agent_instructions()`.

```python
from hygroup.agent.default import AgentSettings, MCPSettings
from hygroup.agent.system import system_agent_instructions
from pydantic_ai.models.google import GoogleModelSettings


--8<-- "hygroup/examples/agents.py:system-agent"
```

The `model` in `AgentSettings` is a Pydantic AI [model name](https://ai.pydantic.dev/api/models/base/), `model_settings` are general Pydantic AI [ModelSettings](https://ai.pydantic.dev/api/settings/) or those of a specific model provider, like [GoogleModelSettings](https://ai.pydantic.dev/models/google/#model-settings).

The configuration returned from `system_agent_config()` is added to the `AgentRegistry` with the `add_config()` method. The registry is persisted to `registry_path` with  `save()`.

```python
import asyncio
from hygroup.agent.registry import AgentRegistry


async def main():
    agent_registry = AgentRegistry(registry_path=".data/agents/registry.json")
    agent_registry.add_config(**system_agent_config())
    # ...

    await agent_registry.save()


if __name__ == "__main__":
    asyncio.run(main())
```

## MCP settings

MCP servers are configured with the `MCPSettings` class. The `server_config` dictionary may include variables of pattern `${VAR_NAME}`. These are substituted with environment variables and [user secrets](tutorial.md#personal-settings) at runtime. User secrets take precedence over environment variables.

Remote MCP servers of Composio [service connectors](service-connectors.md) must be configured with two special variables, a `COMPOSIO_USER_ID` and a toolkit-specific `COMPOSIO_<TOOLKIT>_ID` where `<TOOLKIT>` is the name of a Composio toolkit in uppercase letters, as shown in the following `office` agent configuration.

```python
--8<-- "hygroup/examples/agents.py:office-agent"
```

Values for toolkit-specific variables are generated during [Composio MCP server setup](service-connectors.md#setup-mcp-servers). `COMPOSIO_USER_ID`s are generated during [access authorization](service-connectors.md#authorize-access), and then stored as [user secrets](tutorial.md#personal-settings). 

## Scoped registries

The `AgentRegistries` class supports multiple registries scoped to specific Slack channels. For example, with `.data/agents` as the `root_path`

```python
from hygroup.agent.registry import AgentRegistries


agent_registries = AgentRegistries(root_path=".data/agents")
```

and this registry hierarchy

```
.data/agents/
├── registry.json
├── my-channel-1/
│   └── registry.json
├── my-channel-2/
│   └── registry.json
```

*Hybrid Groups* loads the registries as follows:

- `.data/agents/my-channel-1/registry.json` for Slack channel `my-channel-1`
- `.data/agents/my-channel-2/registry.json` for Slack channel `my-channel-2`
- `.data/agents/registry.json` for all other Slack channels
