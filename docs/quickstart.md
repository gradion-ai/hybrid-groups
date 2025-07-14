# Quickstart

## App installation

Follow the [installation](installation.md) instructions for setting up the development environment and installing the Slack and GitHub apps.

## Agent registration

Register example agents by running the following command. Without any additional API keys, this will add agents `general` and `weather` to the agent registry.

```shell
python demo/register_agents.py
```

!!! Hint

    Other agents in the [demo/register_agents.py](https://github.com/gradion-ai/hybrid-groups/blob/main/demo/register_agents.py) script require additional API keys for running their MCP servers. These can be added to `.env` if sharing API keys among users is acceptable. For running MCP servers with user-specific API keys, users need to add them as user secrets in the Slack app's home view.

## App server

To serve the Slack app, run:

```shell
python -m hygroup.scripts.server --gateway slack
```

To serve the GitHub app, run:

```shell
python -m hygroup.scripts.server --gateway github
```

The GitHub app server additionally requires a [smee.io](https://smee.io/) channel for webhook payload delivery. Start a new channel on the [smee.io](https://smee.io/) page, install the [smee client](https://github.com/probot/smee-client) and connect to the channel with your `channel-id`:

```shell
smee -u https://smee.io/<channel-id> -t http://127.0.0.1:8000/api/v1/github-webhook
```

## Usage example

Activate the `weather` agent via background reasoning by entering e.g.

```markdown
how's the weather in vienna?
```

in the channel where the Slack app was added

<div class="image-zoom quickstart-image">
  <a href="../images/quickstart/quickstart-1.png" target="_blank"><img src="../images/quickstart/quickstart-1.png" class="thumbnail"></a>
  <a href="../images/quickstart/quickstart-1.png" target="_blank" class="large-link"><img src="../images/quickstart/quickstart-1.png" class="large"></a>
</div>

or in the description of a new GitHub issue:

<div class="image-zoom quickstart-image">
  <a href="../images/quickstart/quickstart-2.png" target="_blank"><img src="../images/quickstart/quickstart-2.png" class="thumbnail"></a>
  <a href="../images/quickstart/quickstart-2.png" target="_blank" class="large-link"><img src="../images/quickstart/quickstart-2.png" class="large"></a>
</div>
