FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    curl \
    wget \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p /opt/conda \
    && rm /tmp/miniconda.sh

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN npm install -g smee-client

ENV PATH="/opt/conda/bin:${PATH}"
ENV PATH="/root/.local/bin:${PATH}"

RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main \
    && conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r \
    && conda update -n base -c defaults conda

WORKDIR /app

COPY environment.yml /app/

RUN conda env create -f /app/environment.yml -n hybrid-groups

COPY pyproject.toml poetry.lock /app/
RUN poetry config virtualenvs.create false
RUN conda run --no-capture-output -n hybrid-groups poetry install --no-root

COPY hygroup /app/hygroup
COPY demo /app/demo
COPY logging.yaml /app/
COPY docker/setup.sh /app/
COPY docker/server.sh /app/
COPY docker/entrypoint.sh /app/
RUN chmod +x /app/setup.sh /app/server.sh /app/entrypoint.sh

EXPOSE 8000
EXPOSE 8801

ENTRYPOINT ["/bin/bash", "-c", "source /opt/conda/etc/profile.d/conda.sh && conda activate hybrid-groups && /app/entrypoint.sh \"$@\"", "--"]
