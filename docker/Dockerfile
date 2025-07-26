FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv version 0.8.3
COPY --from=ghcr.io/astral-sh/uv:0.8.3 /uv /uvx /bin/

# Install smee-client globally
RUN npm install -g smee-client

# Set working directory
WORKDIR /app

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock /app/

# Install Python dependencies using uv (skip project install to avoid git dependency)
RUN uv sync --locked --no-dev --no-install-project

# Copy application files
COPY hygroup /app/hygroup
COPY demo /app/demo
COPY logging.yaml /app/
COPY docker/setup.sh /app/
COPY docker/server.sh /app/
COPY docker/entrypoint.sh /app/
RUN chmod +x /app/setup.sh /app/server.sh /app/entrypoint.sh

# Expose ports
EXPOSE 8000
EXPOSE 8801

# Use uv to run the entrypoint with activated virtual environment
ENTRYPOINT ["/bin/bash", "-c", "source /app/.venv/bin/activate && /app/entrypoint.sh \"$@\"", "--"]
