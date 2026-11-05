FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/opt/fastembed_cache \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY cisco_meraki_mcp ./cisco_meraki_mcp
RUN uv sync --locked --no-dev

# Pré-télécharge le modèle d'embedding dans l'image
RUN /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

RUN useradd -m app && chown -R app /app /opt/fastembed_cache
USER app
EXPOSE 8080
CMD ["/app/.venv/bin/cisco-meraki-mcp"]
