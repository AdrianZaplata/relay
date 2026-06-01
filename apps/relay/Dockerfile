# Relay service image — runs both the API and the ingestor (different commands).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install runtime dependencies + the package (dev deps excluded).
COPY pyproject.toml ./
COPY relay ./relay
RUN uv pip install --system --no-cache .

EXPOSE 8000

# Default command runs the API; compose overrides it for the ingestor.
CMD ["uvicorn", "relay.api:app", "--host", "0.0.0.0", "--port", "8000"]
