"""Device fleet simulator — the telemetry producer.

Polls the API for active assets and, every tick, emits telemetry events to the
Kafka `telemetry` topic. Events are keyed by asset_id so all readings for one
asset land on the same partition, preserving per-asset ordering and letting the
topic scale out by partition. The simulator stays decoupled from the database —
it only talks to the public API, like a real device backend would.
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from aiokafka import AIOKafkaProducer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("relay.simulator")

API_BASE = os.environ.get("RELAY_API_BASE", "http://api:8000")
BOOTSTRAP = os.environ.get("RELAY_KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
TOPIC = os.environ.get("RELAY_TELEMETRY_TOPIC", "telemetry")
INTERVAL = float(os.environ.get("RELAY_SIM_INTERVAL", "2.0"))

# Per-asset signal state so values evolve smoothly instead of jumping randomly.
_state: dict[int, dict[str, float]] = {}


def _metrics_for(asset_id: int) -> dict[str, float]:
    s = _state.setdefault(
        asset_id,
        {
            "battery": random.uniform(60, 95),
            "temperature": random.uniform(20, 30),
            "speed": random.uniform(0, 22),
            "lat": 52.520 + random.uniform(-0.05, 0.05),
            "lng": 13.405 + random.uniform(-0.05, 0.05),
        },
    )
    s["battery"] -= random.uniform(0.0, 0.8)
    if s["battery"] < 12:  # simulate a battery swap / recharge
        s["battery"] = random.uniform(85, 98)
    s["temperature"] += random.uniform(-0.6, 0.6)
    # Pedelec assist is capped at 25 km/h (EU); random-walk within [0, 25].
    s["speed"] = min(25.0, max(0.0, s["speed"] + random.uniform(-4, 4)))
    s["lat"] += random.uniform(-0.0012, 0.0012)
    s["lng"] += random.uniform(-0.0012, 0.0012)
    return {
        "battery": round(s["battery"], 2),
        "temperature": round(s["temperature"], 2),
        "speed": round(s["speed"], 1),
        "lat": round(s["lat"], 5),
        "lng": round(s["lng"], 5),
    }


async def _active_assets(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{API_BASE}/assets")
    resp.raise_for_status()
    return [a for a in resp.json() if a["status"] == "active"]


async def _start_producer() -> AIOKafkaProducer:
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: str(k).encode("utf-8"),
        acks="all",  # wait for replicas — durability over throughput
    )
    for attempt in range(1, 31):
        try:
            await producer.start()
            return producer
        except Exception as exc:  # noqa: BLE001
            log.warning("kafka not ready (attempt %d/30): %s", attempt, exc)
            await asyncio.sleep(2)
    raise RuntimeError("kafka did not become available")


async def run() -> None:
    producer = await _start_producer()
    log.info("producing telemetry to topic=%s every %.1fs", TOPIC, INTERVAL)
    sent = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            while True:
                try:
                    assets = await _active_assets(client)
                except Exception as exc:  # noqa: BLE001
                    log.warning("could not fetch assets: %s", exc)
                    assets = []

                now = datetime.now(timezone.utc).isoformat()
                for asset in assets:
                    asset_id = asset["id"]
                    for metric, value in _metrics_for(asset_id).items():
                        event = {
                            "schema_version": 1,
                            "asset_id": asset_id,
                            "metric": metric,
                            "value": value,
                            "recorded_at": now,
                            "event_id": str(uuid4()),
                        }
                        # key=asset_id -> same partition per asset (ordering).
                        await producer.send_and_wait(TOPIC, key=asset_id, value=event)
                        sent += 1
                if assets:
                    log.info("emitted readings for %d active assets (total sent=%d)", len(assets), sent)
                await asyncio.sleep(INTERVAL)
        finally:
            await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
