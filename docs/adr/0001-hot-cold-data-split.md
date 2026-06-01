# ADR 0001 — Hot/cold data split for telemetry

**Status:** accepted · **Context:** a connected e-bike fleet emits telemetry continuously

## Context

Two very different access patterns sit on the same data:

- **Operational (hot):** an operator looking at the console needs *"where is each
  bike right now, what's its battery, is it in maintenance"* — small, recent, queried
  constantly, latency-sensitive.
- **Analytical (cold):** utilisation, battery-health trends, time-in-maintenance need
  *months* of raw history — huge, append-only, scanned in batch, latency-tolerant.

Serving both from one fat table optimises for neither and gets expensive fast.

## Decision

Split by temperature:

- **PostgreSQL = hot store.** Current asset state + a recent window of telemetry the
  dashboard queries. Indexed for point/range reads.
- **Object-storage data lake = cold store.** Cheap, high-volume raw history.
- **Scheduled rollups** (a cron job here; **Airflow** in production) aggregate cold
  data into analytics tables.

## Consequences

- Two stores to keep coherent; the lake is eventually-consistent for analytics. Fine —
  analytics doesn't need second-fresh data.
- The hot store stays small and fast regardless of how much history accumulates.

## At production scale

Keep PostgreSQL thin: a rolling recent window + current state. Tier older telemetry to
the lake (or a TSDB) and let the analytics layer own the long tail. This is exactly the
platform's **PostgreSQL Flex + Object Storage + Airflow** shape — Relay models it in
miniature (the lake/rollup half is sketched here, see [TRADEOFFS](../TRADEOFFS.md)).
