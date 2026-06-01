# ADR 0003 — Event-driven telemetry ingestion via Kafka

**Status:** accepted

## Context

Telemetry is a continuous, high-rate stream from many devices. Ingestion must:

- absorb bursts and survive brief consumer outages without dropping data,
- scale **independently** of read/query traffic,
- preserve per-asset ordering,
- never double-count a reading that gets redelivered.

A synchronous HTTP write per reading couples device uptime to API uptime and makes
back-pressure the device's problem. A log decouples them.

## Decision

A **Kafka** topic (Redpanda locally) sits between producers and storage:

```
device/simulator ──produce(key=asset_id)──▶ topic "telemetry" (3 partitions)
                                                   │  consumer group
                                                   ▼
                                              ingestor ──idempotent write──▶ PostgreSQL
```

- **Keyed by `asset_id`** → all readings for one bike land on one partition →
  per-asset ordering preserved, and the topic scales out by partition.
- **Separate `ingestor` service** from the query API (same codebase, different command)
  → ingest throughput and read throughput scale on independent axes.
- **Delivery: at-least-once.** `enable_auto_commit=False`; the consumer commits its
  offset *only after* the reading is persisted.
- **Idempotent writer** keyed on the unique `event_id`: a redelivery after a crash is a
  no-op. At-least-once delivery + idempotent write = **effectively exactly-once where it
  matters** (the stored data), without the cost/myth of exactly-once delivery.

## Consequences

- More moving parts than a direct POST; eventual consistency between event time and DB
  visibility (sub-second here).
- A malformed ("poison") message must not wedge the consumer — it's logged and skipped
  (a dead-letter topic in production).

## At production scale

- More partitions + more ingestor replicas in the consumer group.
- **Schema registry** (Avro/Protobuf) replaces the JSON `schema_version` envelope.
- Dead-letter topic + alerting on consumer lag.

This mirrors the platform's stated core: *"services communicate through Kafka topics,
enabling loose coupling and independent scaling."*
