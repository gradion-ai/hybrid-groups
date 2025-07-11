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

# Install Node.js 20 from NodeSource repository
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p /opt/conda \
    && rm /tmp/miniconda.sh

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN npm install -g smee-client

ENV PATH="/opt/conda/bin:${PATH}"
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY environment.yml /app/
RUN conda env create -f /app/environment.yml -n hybrid-groups && conda init bash

COPY pyproject.toml poetry.lock /app/
RUN poetry config virtualenvs.create false
RUN conda run --no-capture-output -n hybrid-groups poetry install --no-root

COPY hygroup /app/hygroup
COPY examples /app/examples
COPY logging.yaml /app/
COPY docker/server.sh /app/
RUN chmod +x /app/server.sh

EXPOSE 8000
EXPOSE 8001

CMD ["/bin/bash", "-c", "source /opt/conda/etc/profile.d/conda.sh && conda activate hybrid-groups && /app/server.sh"]
