# Application server

## Slack

To serve the Slack app with the provided example agents, run:

```shell
python -m hygroup.scripts.server \
  --gateway slack \
  --factory-module hygroup.factory.example
```

To enable manual approval of agent actions via [ephemeral messages](https://api.slack.com/surfaces/messages#ephemeral), use the `--user-channel slack` option:

```shell
python -m hygroup.scripts.server \
  --gateway slack \
  --factory-module hygroup.factory.example \
  --user-channel slack
```

## GitHub

To serve the GitHub app with the provided example agents, run:

```shell
python -m hygroup.scripts.server \
  --gateway github \
  --factory-module hygroup.factory.example
```

The GitHub app server additionally requires a [smee.io](https://smee.io/) channel for webhook payload delivery to the local server. A channel is generated during the [GitHub app setup](installation.md#github-app)  and stored in the `.env` file as `GITHUB_APP_WEBHOOK_URL`. To connect to the channel, install the [smee client](https://github.com/probot/smee-client) and run:

```shell
source .env \
&& smee -u $GITHUB_APP_WEBHOOK_URL -t http://127.0.0.1:8000/api/v1/github-webhook
```
