FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .python-version README.md ./
COPY src ./src
COPY web ./web

RUN uv sync --no-dev

ENV LOYALTYDESK_HOST=0.0.0.0
ENV LOYALTYDESK_PORT=3847
ENV LOYALTYDESK_DATA_DIR=/app/data/warehouse
ENV LOYALTYDESK_TRACE_DIR=/app/data/traces

EXPOSE 3847

CMD ["uv", "run", "loyaltydesk", "serve", "--host", "0.0.0.0", "--port", "3847"]
