# Tutorial

This tutorial demonstrates how to install and use the *Hybrid Groups* Slack app.

## Initial setup

### Python package

Create a minimal `hybrid-groups-tutorial` project and install the `hybrid-groups` package:

```bash
uv init --bare --python 3.11 hybrid-groups-tutorial
cd hybrid-groups-tutorial
uv add hybrid-groups
```

### Slack app

Install the *Hybrid Groups* Slack app in a Slack workspace by launching the installation wizard and following the instructions on the screen.

```bash
uv run python -m hygroup.setup.apps slack
```

After installation, you should see the following variables in a `.env` file:

```env title=".env"
SLACK_BOT_TOKEN=...
SLACK_BOT_ID=...
SLACK_APP_TOKEN=...
SLACK_APP_USER_ID=...
```

### Slack channel

Go to the Slack workspace where you installed the app and create a channel. In the channel's menu, `Open channel details` -> `Integrations` -> `Add apps`, and select the `Hybrid Groups` app. 

### API keys

Add a [Gemini API key](https://aistudio.google.com/apikey) and a [Brave Search API key](https://api-dashboard.search.brave.com/app/keys) to the `.env` file:

```env title=".env"
GEMINI_API_KEY=...  # required
BRAVE_API_KEY=...  # optional
```

Adding a `BRAVE_API_KEY` to `.env` enables all users to use this key for web search via the Brave Search API. Alternatively, users can add a `BRAVE_API_KEY` to their [secrets](#personal-settings) in the Slack app's home view, for searching with their personal API keys.

## Example agents

*Hybrid Groups* comes with example agents and a group reasoner defined in the [`hygroup.factory.example`](https://github.com/gradion-ai/hybrid-groups/blob/main/hygroup/factory/example.py) module:

- The group reasoner monitors group chats and decides whether to stay silent or generate a query for the `system` agent. It transforms group chat utterances to agent instructions, depending on criteria and rules defined in its [system prompt](https://github.com/gradion-ai/hybrid-groups/blob/main/hygroup/factory/prompts/reasoner.md).
- The `system` agent receives instructions from the group reasoner. It is configured with a [Brave Search MCP server](https://github.com/brave/brave-search-mcp-server), a [weather forecast](https://github.com/gradion-ai/hybrid-groups/blob/main/hygroup/examples/weather.py) tool and can use the `math` and `office` agents as subagents.
- The `math` agent can execute Python code for calculations, data analysis, and visualizations. It is configured with an [ipybox MCP server](https://gradion-ai.github.io/ipybox/mcp-server/) for secure code execution in a sandbox.
- The `office` agent can manage a user's Gmail, Google Calendar, and Google Drive. It uses [service connectors](#service-connectors) to access these services on behalf of individual users. The `office` agent requires an `OPENAI_API_KEY` in `.env` as it uses `openai:gpt-5-mini` as model.

    ```env title=".env"
    OPENAI_API_KEY=...
    ```

!!! Info "Using your own agents"

    To use your own agents and group reasoner, provide their factory module name as argument to the `--factory-module` command line option when starting the [application server](#application-server). You can also configure [channel-specific](application-server.md#channel-specific-agents) agents and group reasoners with the `--channel-factory-module` option.

## Application server

Start the Slack [application server](application-server.md) with:

```shell
uv run python -m hygroup.scripts.server \
  --gateway slack \
  --factory-module hygroup.factory.example
```

To list the example agents, start typing `/hy` in the message box of the created [Slack channel](#slack-channel), select the `/hygroup-agents` slash command and press `Enter`:
 
 ![Slash command for listing registered agents](images/tutorial/commands/cmd-agents.png)
 
 You should see a list of registered agents (except the group reasoner):

![List of registered example agents](images/tutorial/commands/cmd-agents-result.png)

## Personal settings

Click on the `Hybrid Groups` app in Slack, then the `Home` tab to see your personal settings. These are your preferences (agent response style, ...) and your secrets (API keys, ...). In this example, the user provides his own `BRAVE_API_KEY` which takes precedence over the default `BRAVE_API_KEY` in the `.env` file.

![Personal settings](images/tutorial/home-view.png)

## Group sessions

Users and agents collaborate in group sessions, corresponding to [threads](https://slack.com/help/articles/115000769927-Use-threads-to-organize-discussions) in Slack. The group reasoner monitors :eyes: all messages and decides whether to delegate to the `system` agent :robot: or stay silent :ballot_box_with_check:.

![System agent](images/tutorial/session-1.png)

## Session persistence

Group messages and agent states are persisted. After an [application server](#application-server) restart, group sessions can be resumed. New messages added to Slack threads during an application server downtime are processed when the server is up again.

## Service connectors

!!! Note "Composio integration"

    *Hybrid Groups* uses [Composio](https://composio.dev/) to connect to 250+ services, like Gmail, Notion, Figma, etc. Follow [these setup instructions](service-connectors.md) for using service connectors. 

To enable the `office` agent to access Gmail on behalf of individual users, they must authorize access to their Gmail accounts by running the `/hygroup-connect gmail` command in Slack. This needs to be done only once per user.

![Connect command](images/tutorial/commands/cmd-connect.png)

The system responds with a link to initiate the OAuth flow for Gmail:

![Composio toolkits](images/tutorial/commands/cmd-connect-result-2.png)

Click on the link and follow the instructions on the OAuth consent screen. After successful authorization, the `/hygroup-connect` command should show the Composio `gmail` toolkit as :white_check_mark: connected. You are now ready to use your Gmail account via the `office` agent.

![Composio toolkits](images/tutorial/commands/cmd-connect-result-3.png)

!!! Failure "Access restrictions"

    Users can only access their own Gmail account, never those of other users. Users **never** have access to service accounts of other users.

In the following example, the system agent uses an `office` subagent to get email statistics from the inboxes of two users.

![Access Gmail on behalf of individual users](images/tutorial/connectors.png)

## Media attachments

Users can attach media files (images, videos, sound files, ...) and documents (PDFs, ...) to Slack messages for being processed by agents. Attachments are also accessible to subagents.

![Media attachments](images/tutorial/attachments.png)

## Action approval

Users can be requested to approve actions that are executed on their behalf by starting the application server with the `--user-channel slack` option:

```shell
uv run python -m hygroup.scripts.server --gateway slack --user-channel slack
```

Approval requests are sent to the initiating user as [ephemeral messages](https://docs.slack.dev/messaging/#ephemeral), visible only to that user. Users can choose to approve an action once, for the current session, always, or deny execution. Relevant for an action is the tool name only, not the arguments.

![Action approval](images/tutorial/approval.png)

## Magic commands

Magic commands are frequently used prompts saved under a custom name. Magic commands are managed with the `/hygroup-command` slash command in Slack.

![Magic commands](images/tutorial/commands/cmd-command.png)

For example, to create and `save` a `weather` magic command that gets the weather of the three largest cities of a country, submit the following message:

![Save magic command](images/tutorial/commands/cmd-command-save.png)

The system saves the magic command for the calling user, and should respond with:

![Save magic command result](images/tutorial/commands/cmd-command-save-result.png)

For executing a magic command, start a message with `%` followed by the command name e.g. `%weather`. Text following the command substitutes the `{ARGUMENTS}` variable. If the magic command doesn't contain an `{ARGUMENTS}` variable, the text is appended.

![Execute magic command](images/tutorial/commands/cmd-command-exec.png)

!!! Info

    Magic commands in *Hybrid Groups* are similar to [custom slash commands](https://docs.anthropic.com/en/docs/claude-code/slash-commands#custom-slash-commands) in Claude Code.
