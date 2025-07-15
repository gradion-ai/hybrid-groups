#!/bin/bash

export PYTHONPATH=.

SERVER_HOST=${SERVER_HOST:-"localhost"}

# Assert that .env file exists in data directory and create symlink to app directory
if [ -f /app/.data/.env ]; then
    [ -e /app/.env ] && rm -f /app/.env
    ln -s /app/.data/.env /app/.env
fi

# Validate gateway
if [ "$GATEWAY" != "slack" ] && [ "$GATEWAY" != "github" ]; then
    echo "Error: Unknown GATEWAY type: $GATEWAY"
    echo "Supported gateways: github, slack"
    exit 1
fi

 # Check if configuration already exists
if [ -f .env ]; then
    set -a
    source .env
    set +a

    CONFIG_EXISTS=false
    if [ "$GATEWAY" = "slack" ]; then
        if [ -n "$SLACK_APP_ID" ]; then
            CONFIG_EXISTS=true
        fi
    elif [ "$GATEWAY" = "github" ]; then
        if [ -n "$GITHUB_APP_WEBHOOK_URL" ]; then
            CONFIG_EXISTS=true
        fi
    fi

    if [ "$CONFIG_EXISTS" = true ]; then
        echo "Error: Configuration already exists for gateway '$GATEWAY'"
        echo "Configuration file: /app/.data/.env"
        exit 1
    fi
fi

# Run setup command
if [ "$GATEWAY" = "slack" ]; then
    exec python -m hygroup.setup.apps slack --port 8801 --host ${SERVER_HOST} --no-browser
elif [ "$GATEWAY" = "github" ]; then
    exec python -m hygroup.setup.apps github --port 8801 --host ${SERVER_HOST} --no-browser
else
    echo "Error: Unknown GATEWAY type: $GATEWAY"
    exit 1
fi

echo ""
echo "Setup completed successfully!"
exit 0
