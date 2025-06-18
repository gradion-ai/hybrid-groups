# Set up the Slack Integration

This guide will show you how to integrate Hybrid Groups with Slack using the [Slack App Manifest Flow](https://api.slack.com/reference/manifests).

## Prerequisites

- **Slack workspace** with admin permissions
- **Slack account** with ability to create apps

## Create the Slack App

### 1. Start the setup script

```bash
python -m hygroup.setup.apps slack
```

A browser opens to the Slack App setup page.

### 2. Configure your app's settings

- **App Name**: A unique identifier (e.g., "My Slack Application Agent"). Becomes your bot's display name in Slack.
- **Configuration Token**: Required to create apps via API. Get this from [api.slack.com/apps](https://api.slack.com/apps).

<img src="images/app_setup/slack/01_slack_setup_page.png" alt="Slack Setup Page" width="600">

### 3. Generate a configuration token

Navigate to [api.slack.com/apps](https://api.slack.com/apps) and find "Your App Configuration Tokens" section. Click `Generate Token` and copy the access token (starts with `xoxe`).

<img src="images/app_setup/slack/02_slack_app_config_token.png" alt="Slack Configuration Token" width="600">

### 4. Create the app on Slack

Paste the configuration token in the setup page and click `Create Slack App` to create your application with Slack.

After successful creation you are redirected to the token configuration page.

<img src="images/app_setup/slack/03_slack_app_created.png" alt="Slack App Created" width="600">

## Configure authentication tokens

Two tokens are required for the Slack integration:
- **App-Level Token**: Enables Socket Mode connections
- **Bot User OAuth Token**: Authenticates API calls

### 1. Generate App-Level Token

Click `Slack App-Level Tokens section` on the configuration page to navigate to your app's Basic Information.

<img src="images/app_setup/slack/04_slack_app_token_overview.png" alt="Token Overview" width="600">

In the App-Level Tokens section:
1. Click `Generate Token and Scopes`
2. Name your token (e.g., "App Token")
3. Add the `connections:write` scope
4. Click `Generate`
5. Copy the token (starts with `xapp`)

<img src="images/app_setup/slack/05_slack_app_token_created.png" alt="App-Level Token Created" width="600">

Return to the setup page and paste the App-Level Token.

### 2. Install the app to your workspace

Click `Slack Install App section` on the configuration page to navigate to the Install App section.

<img src="images/app_setup/slack/06_slack_install_app.png" alt="Install App" width="600">

Click `Install to [workspace name]` and review the required permissions.

<img src="images/app_setup/slack/07_slack_install_app_permissions.png" alt="Authorize Permissions" width="600">

Click `Allow` to complete the installation. Copy the generated Bot User OAuth Token (starts with `xoxb`).

<img src="images/app_setup/slack/08_slack_install_app_token.png" alt="Bot Token" width="600">

### 3. Complete installation setup

Return to the setup page, ensure both tokens are entered, and click `Complete Setup`.

<img src="images/app_setup/slack/09_slack_complete_setup.png" alt="Complete Setup" width="600">

## Generated Credentials

Upon successful completion of the setup, credentials are automatically saved in your `.env` file.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `SLACK_APP_ID` | App identifier |
| `SLACK_APP_TOKEN` | Authentication token to receive events from Slack |
| `SLACK_BOT_TOKEN` | Authentication token for API calls |
