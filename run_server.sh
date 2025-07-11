#!/bin/bash

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <gateway: github|slack> [options]"
    echo "Options:"
    echo "  --data-dir <path>     Data directory (default: .hybrid_groups_data)"
    echo "  --host <host>         Host address (default: localhost)"
    echo ""
    echo "Examples:"
    echo "  $0 github"
    echo "  $0 github --host 0.0.0.0"
    echo "  $0 github --data-dir /path/to/data --host 192.168.1.100"
    echo "  $0 github /path/to/data localhost  # old positional format still works"
    exit 1
fi

GATEWAY=$1
DATA_DIR=".hybrid_groups_data"
HOST="localhost"

# Parse remaining arguments
shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        *)
            # Handle old positional format for backward compatibility
            if [[ -z "$DATA_DIR_SET" ]]; then
                DATA_DIR="$1"
                DATA_DIR_SET=true
            elif [[ -z "$HOST_SET" ]]; then
                HOST="$1"
                HOST_SET=true
            fi
            shift
            ;;
    esac
done

# Convert to absolute path if relative
if [[ "$DATA_DIR" != /* ]]; then
    DATA_DIR="$(pwd)/$DATA_DIR"
fi

echo "--------------------------------"
echo "Hybrid Groups Application Server"
echo "--------------------------------"
echo "Data directory: $DATA_DIR"
echo "Gateway:        $GATEWAY"
echo "Host:           $HOST"
echo ""

# Check if data directory exists
if [ ! -d "$DATA_DIR" ]; then
    echo "Data directory does not exist. Creating: $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

# Check for .env file
ENV_FILE="$DATA_DIR/.env"
NEED_API_KEY=true

if [ -f "$ENV_FILE" ]; then
    # Check if GEMINI_API_KEY exists and has a non-empty value
    if grep -q "^GEMINI_API_KEY=..*" "$ENV_FILE"; then
        NEED_API_KEY=false
    fi
fi

# Prompt for key if needed
if [ "$NEED_API_KEY" = true ]; then
    echo "Please create and enter your GEMINI_API_KEY (https://aistudio.google.com/apikey):"
    read -p "GEMINI_API_KEY: " API_KEY

    if [ -z "$API_KEY" ]; then
        echo "Error: API key cannot be empty"
        exit 1
    fi

    if [ -f "$ENV_FILE" ]; then
        # Check if GEMINI_API_KEY line exists
        if grep -q "^GEMINI_API_KEY=" "$ENV_FILE"; then
            # Replace the line
            sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=$API_KEY/" "$ENV_FILE"
        else
            # Add to existing file
            echo "GEMINI_API_KEY=$API_KEY" >> "$ENV_FILE"
        fi
    else
        # Create new file
        echo "GEMINI_API_KEY=$API_KEY" > "$ENV_FILE"
    fi
    echo ""
fi

docker run \
  --name hygroup \
  -v "$DATA_DIR":/app/.data \
  -e GATEWAY="$GATEWAY" \
  -e SERVER_HOST="$HOST" \
  -p 8001:8001 \
  hybrid-groups-hygroup
