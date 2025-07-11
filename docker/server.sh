#!/bin/bash

# Check if .env file exists in data directory and create symlink
if [ -f /app/.data/.env ]; then
    [ -e /app/.env ] && rm -f /app/.env
    ln -s /app/.data/.env /app/.env
else
    echo "Error: .env file not found"
    echo "Please create a .env file in your data directory with the following environment variable:"
    echo "GEMINI_API_KEY=<your-api-key>"
    exit 1
fi

export PYTHONPATH=.

# Convert GATEWAY to lowercase for case-insensitive comparisons
GATEWAY_LOWER=$(echo "$GATEWAY" | tr '[:upper:]' '[:lower:]')

# Variable to track if setup is needed
SETUP_NEEDED=false
SETUP_TYPE=""

# Check if .env file exists
if [ -f .env ]; then
    # Load variables from .env file
    set -a
    source .env
    set +a
    echo "Environment variables loaded from .env file"

    # Check if GEMINI_API_KEY is set
    if [ -z "$GEMINI_API_KEY" ]; then
        echo "Error: GEMINI_API_KEY not found in .env file"
        echo "Please add GEMINI_API_KEY=<your-api-key> to your .env file"
        exit 1
    fi

    # Re-convert GATEWAY to lowercase after loading .env
    GATEWAY_LOWER=$(echo "$GATEWAY" | tr '[:upper:]' '[:lower:]')

    # Check for required variables based on GATEWAY
    if [ "$GATEWAY_LOWER" = "slack" ]; then
        if [ -z "$SLACK_APP_ID" ]; then
            echo "SLACK_APP_ID not found, entering setup mode for Slack"
            SETUP_NEEDED=true
            SETUP_TYPE="slack"
        fi
    elif [ "$GATEWAY_LOWER" = "github" ]; then
        if [ -z "$GITHUB_APP_WEBHOOK_URL" ]; then
            echo "GITHUB_APP_WEBHOOK_URL not found, entering setup mode for GitHub"
            SETUP_NEEDED=true
            SETUP_TYPE="github"
        fi
    fi
else
    echo "Error: .env file not found"
    exit 1
fi

# Check if agents directory exists, if not register agents
if [ ! -d /app/.data/agents ]; then
    echo "Agents directory not found, registering agents..."
    python examples/register_agents.py
fi

# Run setup if needed
if [ "$SETUP_NEEDED" = true ]; then
    echo "Starting setup for $SETUP_TYPE..."
    if [ "$SETUP_TYPE" = "slack" ]; then
        python -m hygroup.setup.apps slack --port 8001 --host 192.168.1.77
    elif [ "$SETUP_TYPE" = "github" ]; then
        python -m hygroup.setup.apps github --port 8001 --host 192.168.1.77
    else
        echo "Error: Unknown GATEWAY type: $GATEWAY"
        exit 1
    fi
    echo "Setup completed"
fi

# Start the application
echo "Starting application with gateway: $GATEWAY"

# Start smee if GATEWAY is github
if [ "$GATEWAY_LOWER" = "github" ]; then
    # Reload .env if it was just created during setup
    if [ -f .env ]; then
        set -a
        source .env
        set +a
        # Re-convert GATEWAY to lowercase after reloading .env
        GATEWAY_LOWER=$(echo "$GATEWAY" | tr '[:upper:]' '[:lower:]')
    fi

    if [ -n "$GITHUB_APP_WEBHOOK_URL" ]; then
        echo "Starting smee gateway with URL: $GITHUB_APP_WEBHOOK_URL"
        smee -u "$GITHUB_APP_WEBHOOK_URL" -t http://127.0.0.1:8000/api/v1/github-webhook &
    fi
fi

python examples/app_server.py --gateway $GATEWAY
