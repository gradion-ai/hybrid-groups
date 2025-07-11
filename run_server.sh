#!/bin/bash

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <gateway: github|slack> [data_directory] [host]"
    echo "Example: $0 github /path/to/data localhost"
    echo "Example: $0 github  # uses .hybrid_groups_data and localhost"
    exit 1
fi

GATEWAY=$1
DATA_DIR=${2:-".hybrid_groups_data"}
HOST=${3:-"localhost"}

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
