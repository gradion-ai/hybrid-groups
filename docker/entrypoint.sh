#!/bin/bash

show_usage() {
    echo "Usage: docker run [docker-options] <image> <command>"
    echo ""
    echo "Commands:"
    echo "  setup <gateway> [options]    Run application setup"
    echo "  server <gateway> [options]   Run application server"
    echo ""
    echo "Gateways:"
    echo "  github                       GitHub gateway"
    echo "  slack                        Slack gateway"
    echo ""
    echo "Setup Options:"
    echo "  --host <host>                Host address (default: localhost)"
    echo ""
    echo "Server Options:"
    echo "  --user-channel <channel>     User channel (slack | terminal)"
    echo ""
    echo "Examples:"
    echo "  docker run --rm -it -v /data:/app/.data -p 8801:8801 <image> setup github"
    echo "  docker run --rm -it -v /data:/app/.data -p 8801:8801 <image> setup github --host 0.0.0.0"
    echo "  docker run --rm -it -v /data:/app/.data -p 8000:8000 <image> server slack"
    echo "  docker run --rm -it -v /data:/app/.data -p 8000:8000 <image> server slack --user-channel slack"
    echo ""
}

# Check if we have at least 2 arguments
if [ $# -lt 2 ]; then
    echo "Error: Missing required arguments"
    echo ""
    show_usage
    exit 1
fi

MODE="$1"
GATEWAY="$2"
shift 2

# Validate mode
if [ "$MODE" != "setup" ] && [ "$MODE" != "server" ]; then
    echo "Error: Unknown mode: $MODE"
    echo "Valid modes: setup, server"
    echo ""
    show_usage
    exit 1
fi

# Validate gateway
GATEWAY_LOWER=$(echo "$GATEWAY" | tr '[:upper:]' '[:lower:]')
if [ "$GATEWAY_LOWER" != "github" ] && [ "$GATEWAY_LOWER" != "slack" ]; then
    echo "Error: Unknown gateway: $GATEWAY"
    echo "Valid gateways: github, slack"
    echo ""
    show_usage
    exit 1
fi

# Set default values
SERVER_HOST="localhost"
USER_CHANNEL=""

# Parse remaining arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            if [ "$MODE" != "setup" ]; then
                echo "Error: --host option is only valid in setup mode"
                exit 1
            fi
            if [ -z "$2" ]; then
                echo "Error: --host requires a value"
                exit 1
            fi
            SERVER_HOST="$2"
            shift 2
            ;;
        --user-channel)
            if [ "$MODE" != "server" ]; then
                echo "Error: --user-channel option is only valid in server mode"
                exit 1
            fi
            if [ -z "$2" ]; then
                echo "Error: --user-channel requires a value"
                exit 1
            fi
            if [ "$2" != "slack" ] && [ "$2" != "terminal" ]; then
                echo "Error: --user-channel must be either 'slack' or 'terminal'"
                exit 1
            fi
            USER_CHANNEL="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
done

# Create .env file in data directory if it doesn't exist
if [ ! -f /app/.data/.env ]; then
    touch /app/.data/.env
fi

export GATEWAY="$GATEWAY_LOWER"
export SERVER_HOST="$SERVER_HOST"
export USER_CHANNEL="$USER_CHANNEL"

# Call the appropriate script based on mode
if [ "$MODE" = "setup" ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                Hybrid Groups Application Setup             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo "Gateway: $GATEWAY_LOWER"
    echo ""

    exec /app/setup.sh
elif [ "$MODE" = "server" ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                Hybrid Groups Application Server            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo "Gateway: $GATEWAY_LOWER"
    echo ""

    exec /app/server.sh
else
    echo "Error: Invalid mode '$MODE'"
    exit 1
fi
