#!/bin/bash

# Check arguments
# if [ $# -lt 1 ]; then
#     echo "Usage: $0 [data_directory]"
#     echo "Example: $0 /path/to/data"
#     echo "Example: $0  # uses .hybrid_groups_data"
#     exit 1
# fi

DATA_DIR=${1:-".hybrid_groups_data"}

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
# ENV_FILE="$DATA_DIR/.env"
# NEED_API_KEY=true

# if [ -f "$ENV_FILE" ]; then
#     echo "Found .env file: $ENV_FILE"
#     # Check if GEMINI_API_KEY exists and has a non-empty value
#     if grep -q "^GEMINI_API_KEY=..*" "$ENV_FILE"; then
#         echo "GEMINI_API_KEY found in .env file"
#         NEED_API_KEY=false
#     else
#         echo "GEMINI_API_KEY not found or empty in .env file"
#     fi
# else
#     echo ".env file not found: $ENV_FILE"
# fi

echo "Starting Docker container..."
docker run -it \
  --entrypoint /bin/bash \
  -v "$DATA_DIR":/app/.data \
  hybrid-groups-hygroup \
   -c "ln -s /app/.data/.env /app/.env && source /opt/conda/etc/profile.d/conda.sh && conda activate hybrid-groups && export PYTHONPATH=. && python examples/register_user.py"
