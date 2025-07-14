# Installation

## Development environment

```bash
conda env create -f environment.yml
conda activate hybrid-groups
poetry install
```

Find more details in [DEVELOPMENT.md](https://github.com/gradion-ai/hybrid-groups/blob/main/DEVELOPMENT.md).

## Slack app

To set up and install the *Hybrid Groups* Slack app to your workspace, run:

```shell
python -m hygroup.setup.apps slack
```

This will add the following variables to your `.env` file:

```env title=".env"
SLACK_BOT_TOKEN=...
SLACK_APP_TOKEN=...
SLACK_APP_ID=...
```

After setup, you must manually add the app to any Slack channels you want it to be active in. You can do this from the channel's menu under `Open channel details` -> `Integrations` -> `Add apps`.

## GitHub app

To set up and install the *Hybrid Groups* GitHub app, run:

```shell
python -m hygroup.setup.apps github
```

This will add the following variables to your `.env` file:

```env title=".env"
GITHUB_APP_ID=...
GITHUB_APP_USERNAME=...
GITHUB_APP_CLIENT_SECRET=...
GITHUB_APP_WEBHOOK_SECRET=...
GITHUB_APP_PRIVATE_KEY_PATH=...
GITHUB_APP_INSTALLATION_ID=...
```
