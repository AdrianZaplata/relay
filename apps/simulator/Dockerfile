# Device fleet simulator — telemetry producer.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv pip install --system --no-cache "aiokafka>=0.11" "httpx>=0.27"

COPY simulator.py .

CMD ["python", "simulator.py"]
