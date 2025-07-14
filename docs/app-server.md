# App server

## Slack

To serve the Slack app, run:

```shell
python -m hygroup.scripts.server --gateway slack
```

This auto-approves all tool executions. To enable manual approval of tool executions via [ephemeral messages](https://api.slack.com/surfaces/messages#ephemeral) use the `--user-channel slack` option:

```shell
python -m hygroup.scripts.server --gateway slack --user-channel slack
```

Alternatively, use a terminal-based, [separate user channel](#separate-user-channel):

```shell
python -m hygroup.scripts.server --gateway slack --user-channel terminal
```

## GitHub

To serve the GitHub app, run:

```shell
python -m hygroup.scripts.server --gateway github
```

The GitHub app server additionally requires a [smee.io](https://smee.io/) channel for webhook payload delivery. Start a new channel on the [smee.io](https://smee.io/) page, install the [smee client](https://github.com/probot/smee-client) and connect to the channel with your `channel-id`:

```shell
smee -u https://smee.io/<channel-id> -t http://127.0.0.1:8000/api/v1/github-webhook
```

This auto-approves all tool execution permissions. In contrast to Slack, the GitHub integration doesn't include a built-in user channel for approving tool execution permissions. The only option is a terminal-based, [separate user channel](#separate-user-channel):

```shell
python -m hygroup.scripts.server --gateway github --user-channel terminal
```

## Terminal

To serve a terminal-based chat client, for demonstration or testing purposes, run:

```shell
python -m hygroup.scripts.server --gateway terminal
```

Then start the client with

```shell
python -m hygroup.scripts.client --username <username>
```

where `<username>` is a username of your choice or a [registered username](user-registry.md). If registered with a user password, provide the same password at login, otherwise leave it empty.

## Separate user channel

A terminal-based, separate user channel for approving tool execution can be established by starting the app server with the `--user-channel terminal` option and then a channel client with:

```shell
python -m hygroup.scripts.channel --username <username>
```

where `<username>` is

- a Slack member id (e.g. `U061F7AURQ6`) when running the app server with `--gateway slack`
- a GitHub username when running the app server with `--gateway github`
- a matching username when running the app server with `--gateway terminal`
- a [registered username](user-registry.md) when running the app server with any `--gateway` argument
