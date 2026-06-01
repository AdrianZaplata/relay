"""Telemetry ingestor — the primary ingestion path.

Consumes the `telemetry` topic and writes each reading to PostgreSQL through the
same idempotent writer the API uses. Runs as its own service (same image as the
API, different command) so ingest throughput scales independently of read traffic.

Delivery semantics: at-least-once. Offsets are committed only *after* a reading
is persisted, and the writer is idempotent on `event_id`, so a redelivery after a
crash is a no-op at the storage layer — effectively exactly-once where it counts.
See docs/adr/0003.
"""

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from .config import settings
from .db import SessionLocal, init_models
from .ingest import persist_reading, reading_from_event
from .log import configure_logging
from .schemas import TelemetryEvent

log = logging.getLogger("relay.ingestor")


async def _start_with_retry(consumer: AIOKafkaConsumer, retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            await consumer.start()
            return
        except Exception as exc:  # noqa: BLE001 - retry until the broker is up
            log.warning("kafka not ready (attempt %d/%d): %s", attempt, retries, exc)
            await asyncio.sleep(delay)
    raise RuntimeError("kafka did not become available")


async def run() -> None:
    configure_logging(settings.log_level)
    await init_models()

    consumer = AIOKafkaConsumer(
        settings.telemetry_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.consumer_group,
        enable_auto_commit=False,  # commit after persist -> at-least-once
        auto_offset_reset="earliest",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    await _start_with_retry(consumer)
    log.info(
        "ingestor consuming",
        extra={"fields": {"topic": settings.telemetry_topic, "group": settings.consumer_group}},
    )

    inserted = duplicates = 0
    try:
        async for msg in consumer:
            try:
                event = TelemetryEvent.model_validate(msg.value)
                async with SessionLocal() as session:
                    if await persist_reading(session, reading_from_event(event)):
                        inserted += 1
                    else:
                        duplicates += 1
                await consumer.commit()
                if (inserted + duplicates) % 25 == 0:
                    log.info(
                        "ingest progress",
                        extra={"fields": {"inserted": inserted, "duplicates": duplicates}},
                    )
            except Exception as exc:  # noqa: BLE001
                # A poison message shouldn't wedge the consumer. In production this
                # goes to a dead-letter topic; here we log, commit, and move on.
                log.exception("dropping unprocessable message: %s", exc)
                await consumer.commit()
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
