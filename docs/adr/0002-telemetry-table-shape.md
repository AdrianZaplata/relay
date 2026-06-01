# ADR 0002 — Telemetry table shape: narrow/long

**Status:** accepted

## Context

A pedelec emits several metrics — `battery`, `speed`, `temperature`, GPS `lat`/`lng`,
and, on a fully digital drivetrain, more over time (motor power, cadence, generator
output). The set of metrics will grow. Each reading is `(asset, metric, value, time)`.

## Decision

Store telemetry **narrow/long**: one row per metric reading, not a wide row with a
column per metric.

```
telemetry(id, asset_id, metric, value, recorded_at, event_id UNIQUE)
index (asset_id, recorded_at)   -- the "recent readings for this bike" query
```

- Adding a new metric is **data, not a migration** — no `ALTER TABLE`, no sparse
  columns for metrics a given asset doesn't emit.
- `event_id` is `UNIQUE` — the idempotency key (see [0003](0003-event-driven-ingestion.md)).
- The composite index serves the dashboard's per-asset time-range query directly.

## Consequences

- More rows than a wide layout; queries filter by `metric`. Acceptable — the index
  makes the hot query cheap, and row volume is the lake's problem, not the hot store's.
- No cross-metric row (e.g. "battery and speed at the exact same instant"); if a use
  case needs that, it's a read-time join/bucket, not a storage decision.

## At production scale

- **Time-partition** the table (monthly/weekly); dropping old data becomes dropping a
  partition, and the hot store only ever holds recent partitions.
- Past a threshold, reach for a **time-series store** (TimescaleDB) or push raw to the
  **data lake** and keep only a rolled-up hot window in PostgreSQL ([0001](0001-hot-cold-data-split.md)).
