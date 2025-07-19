# Quickstart

!!! Tip "Docker"

    As an alternative to a [local environment setup](#app-installation), use our Docker container to install and run the Slack and GitHub apps:

    1. Configure the app type to install and run, `slack` or `github`:
    ```bash
    export APP_TYPE=slack # or "github"
    ```

    2. Setup the app (prints the setup URL to follow in the output) - **only required once per app**:
    ```bash    
    docker run --rm -it \
      -v "$(pwd)/.data-docker":/app/.data \
      -p 8801:8801 \
      ghcr.io/gradion-ai/hybrid-groups:latest \
      setup $APP_TYPE
    ```
    **Important**: when running the container on a remote host, supply the hostname or IP address via the `--host` parameter. After setting up the Slack app, add it to any Slack channels you want it to be active in. You can do this from the channel's menu under `Open channel details` -> `Integrations` -> `Add apps`.
    
    3. Run the server:
    ```bash
    docker run --rm -it \
      -v "$(pwd)/.data-docker":/app/.data \
      ghcr.io/gradion-ai/hybrid-groups:latest \
      server $APP_TYPE
    ```
    To enable [user channels](app-server.md#slack) in Slack, append the `--user-channel slack` option.

    4. Verify with a [usage example](#usage-example) that your installation works.

## App installation

Follow the [installation](installation.md) instructions for setting up a [development environment](installation.md#development-environment) and installing the Slack and GitHub apps.

## Gemini API key

A [GEMINI_API_KEY](https://aistudio.google.com/apikey) is required for background reasoning and by demo agents. Place it in a `.env` file in the project's root directory.

```env title=".env"
GEMINI_API_KEY=...
```

## Agent registration

Register example agents by running the following command. Without any additional API keys, this will add agents `general` and `weather` to the agent registry.

```shell
python demo/register_agents.py
```

!!! Hint

    Other agents in the [demo/register_agents.py](https://github.com/gradion-ai/hybrid-groups/blob/main/demo/register_agents.py) script require additional API keys for running their MCP servers. These can be added to `.env` if sharing API keys among users is acceptable. For running MCP servers with user-specific API keys, users need to add them as user secrets in the Slack app's [home view](images/overview/overview-2.png) or via [user registration](user-registry.md).

## App server

To serve the Slack app, run:

```shell
python -m hygroup.scripts.server --gateway slack
```

To serve the GitHub app, run:

```shell
python -m hygroup.scripts.server --gateway github
```

The GitHub app server additionally requires a [smee.io](https://smee.io/) channel for webhook payload delivery. A channel is generated during the GitHub app setup and stored in the `.env` file as `GITHUB_APP_WEBHOOK_URL`. To connect to the channel, install the [smee client](https://github.com/probot/smee-client) and run:

```shell
source .env \
&& smee -u $GITHUB_APP_WEBHOOK_URL -t http://127.0.0.1:8000/api/v1/github-webhook
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

For directly mentioning the `weather` agent in Slack, use `@weather` at the beginning of a message, in GitHub use `@hybrid-groups/weather` (and replace `hybrid-groups` with the GitHub app name you've chosen).
