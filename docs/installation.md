# Installation

*Hybrid Groups* requires an installation of

- the `hybrid-groups` [Python package](#python-package) locally,
- the [Slack app](#slack-app) in a Slack workspace, or
- the [GitHub app](#github-app) in a GitHub repository

See [Tutorial](tutorial.md) for running and using *Hybrid Groups*.

## Python package

```bash
pip install hybrid-groups
```

## Slack app

For installing the *Hybrid Groups* Slack app in a Slack workspace, launch the setup wizard and follow the instructions on the screen:

```shell
python -m hygroup.setup.apps slack
```
After installation, you should see the following variables in a `.env` in the current working directory (creating a new one if it doesn't exist):

```env title=".env"
SLACK_BOT_TOKEN=...
SLACK_BOT_ID=...
SLACK_APP_TOKEN=...
SLACK_APP_USER_ID=...
```

For using the app, add it to a channel in Slack. In the channel's menu, `Open channel details` -> `Integrations` -> `Add apps`, and select the `Hybrid Groups` app.

## GitHub app

For installing the *Hybrid Groups* GitHub app in a GitHub repository, launch the setup wizard and follow the instructions on the screen:

```shell
python -m hygroup.setup.apps github
```

After installation, you should see the following variables in a `.env` in the current working directory (creating a new one if it doesn't exist):

```env title=".env"
GITHUB_APP_ID=...
GITHUB_APP_USERNAME=...
GITHUB_APP_CLIENT_SECRET=...
GITHUB_APP_WEBHOOK_SECRET=...
GITHUB_APP_PRIVATE_KEY_PATH=...
GITHUB_APP_WEBHOOK_URL...
GITHUB_APP_INSTALLATION_ID=...
```

For serving the GitHub app locally, you additionally need to install the [smee client](https://github.com/probot/smee-client):

```bash
npm install -g smee-client
```
