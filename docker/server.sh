#!/bin/bash

export PYTHONPATH=.

validate_config() {
    if [ ! -f .env ]; then
        echo "Error: Configuration file not found"
        echo "Please run the app setup first"
        exit 1
    fi

    set -a
    source .env
    set +a

    CONFIG_FOUND=false
    if [ "$GATEWAY" = "slack" ]; then
        if [ -n "$SLACK_APP_ID" ]; then
            CONFIG_FOUND=true
        fi
    elif [ "$GATEWAY" = "github" ]; then
        if [ -n "$GITHUB_APP_WEBHOOK_URL" ]; then
            CONFIG_FOUND=true
        fi
    fi

    if [ "$CONFIG_FOUND" = false ]; then
        echo "Error: Configuration not found for gateway '$GATEWAY'"
        echo "Please run the app setup to configure the gateway"
        exit 1
    fi
}

prompt_for_api_keys() {
    NEED_GEMINI_KEY=true
    if [ -f .env ]; then
        if grep -q "^GEMINI_API_KEY=..*" .env; then
            NEED_GEMINI_KEY=false
        fi
    fi

    # Prompt for GEMINI_API_KEY if not found (mandatory)
    if [ "$NEED_GEMINI_KEY" = true ]; then
        echo "Please enter your GEMINI_API_KEY. This key is used for background reasoning and by demo agents. (https://aistudio.google.com/apikey):"
        read -s -p "GEMINI_API_KEY (input hidden): " API_KEY
        echo ""

        if [ -z "$API_KEY" ]; then
            echo "Error: GEMINI API key cannot be empty"
            exit 1
        fi

        if [ -f .env ]; then
            if grep -q "^GEMINI_API_KEY=" .env; then
                sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=$API_KEY/" .env
            else
                echo "" >> .env
                echo "GEMINI_API_KEY=$API_KEY" >> .env
            fi
        else
            echo "GEMINI_API_KEY=$API_KEY" > .env
        fi
        echo ""
    fi

    # Check and prompt for optional BRAVE_API_KEY (only on first startup)
    if [ "$NEED_GEMINI_KEY" = true ]; then
        NEED_BRAVE_KEY=true
        if [ -f .env ]; then
            if grep -q "^BRAVE_API_KEY=..*" .env; then
                NEED_BRAVE_KEY=false
            fi
        fi

        if [ "$NEED_BRAVE_KEY" = true ]; then
            echo "Enter your BRAVE_API_KEY to enable the demo **Search Agent** (Press Enter to skip)"
            read -s -p "BRAVE_API_KEY (input hidden): " BRAVE_KEY
            echo ""

            if [ ! -z "$BRAVE_KEY" ]; then
                if grep -q "^BRAVE_API_KEY=" .env; then
                    sed -i "s/^BRAVE_API_KEY=.*/BRAVE_API_KEY=$BRAVE_KEY/" .env
                else
                    echo "" >> .env
                    echo "BRAVE_API_KEY=$BRAVE_KEY" >> .env
                fi
            fi
            echo ""
        fi
    fi
}

register_agents() {
    if [ ! -d /app/.data/agents ]; then
        echo ""
        echo "Registering demo agents in agent registry..."
        echo ""
        python demo/register_agents.py
    fi
}

start_server() {
    if [ "$GATEWAY" = "github" ]; then
        if [ -n "$GITHUB_APP_WEBHOOK_URL" ]; then
            echo ""
            echo "Starting smee gateway with URL: $GITHUB_APP_WEBHOOK_URL"
            echo ""
            smee -u "$GITHUB_APP_WEBHOOK_URL" -t http://127.0.0.1:8000/api/v1/github-webhook &
        fi
    fi

    echo "🚀 Starting Application server..."
    echo ""
    if [ -n "$USER_CHANNEL" ]; then
        exec python -m hygroup.scripts.server --gateway $GATEWAY --user-channel $USER_CHANNEL
    else
        exec python -m hygroup.scripts.server --gateway $GATEWAY
    fi
}

# Assert that .env file exists in data directory and create symlink to app directory
if [ -f /app/.data/.env ]; then
    [ -e /app/.env ] && rm -f /app/.env
    ln -s /app/.data/.env /app/.env
else
    echo "Error: .env file not found"
    exit 1
fi

# Validate gateway
if [ "$GATEWAY" != "slack" ] && [ "$GATEWAY" != "github" ]; then
    echo "Error: Unknown GATEWAY type: $GATEWAY"
    echo "Supported gateways: github, slack"
    exit 1
fi

validate_config

prompt_for_api_keys

register_agents

start_server
