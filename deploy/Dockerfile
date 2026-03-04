FROM python:3.13-slim

# Install system dependencies (ttyd from GitHub releases, not in Debian repos)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor git curl && \
    rm -rf /var/lib/apt/lists/*

ARG TTYD_VERSION=1.7.7
RUN ARCH=$(uname -m) && \
    curl -Lo /usr/local/bin/ttyd \
      "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${ARCH}" && \
    chmod +x /usr/local/bin/ttyd

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files first for layer caching
WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install Python dependencies (cached unless pyproject.toml/uv.lock change)
RUN uv sync --no-dev --no-install-project

# Copy application source
COPY . .

# Install the project itself (uses cached deps from above)
RUN uv sync --no-dev

# Copy deployment configs
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/supervisord.conf /etc/supervisor/conf.d/satellite.conf

EXPOSE 8080 7575

CMD ["supervisord", "-n"]
