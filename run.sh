#!/bin/bash

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <gateway: github|slack> [data_directory]"
    echo "Example: $0 github /path/to/data"
    echo "Example: $0 github  # uses .hybrid_groups_data"
    exit 1
fi

GATEWAY=$1
DATA_DIR=${2:-".hybrid_groups_data"}

# Convert to absolute path if relative
if [[ "$DATA_DIR" != /* ]]; then
    DATA_DIR="$(pwd)/$DATA_DIR"
fi

echo "Using data directory: $DATA_DIR"

# Check if data directory exists
if [ ! -d "$DATA_DIR" ]; then
    echo "Data directory does not exist. Creating: $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

# Check for .env file
ENV_FILE="$DATA_DIR/.env"
NEED_API_KEY=true

if [ -f "$ENV_FILE" ]; then
    echo "Found .env file: $ENV_FILE"
    # Check if GEMINI_API_KEY exists and has a non-empty value
    if grep -q "^GEMINI_API_KEY=..*" "$ENV_FILE"; then
        echo "GEMINI_API_KEY found in .env file"
        NEED_API_KEY=false
    else
        echo "GEMINI_API_KEY not found or empty in .env file"
    fi
else
    echo ".env file not found: $ENV_FILE"
fi

# Prompt for key if needed
if [ "$NEED_API_KEY" = true ]; then
    echo "Please enter your GEMINI_API_KEY:"
    read -p "API Key: " API_KEY

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
    echo "GEMINI_API_KEY saved to $ENV_FILE"
fi

# Print data directory
echo "Data directory: $DATA_DIR"

# Stop and remove existing container if it exists
if docker ps -a --format "table {{.Names}}" | grep -q "^hygroup$"; then
    echo "Stopping and removing existing hygroup container..."
    docker stop hygroup >/dev/null 2>&1
    docker rm hygroup >/dev/null 2>&1
fi

echo "Starting Docker container..."
docker run \
  --name hygroup \
  -v "$DATA_DIR":/app/.data \
  -e GATEWAY="$GATEWAY" \
  -p 8000:8000 \
  -p 8001:8001 \
  hybrid-groups-hygroup
