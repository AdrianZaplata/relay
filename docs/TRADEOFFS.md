# Tradeoffs — what I deliberately left out, and how I'd do it for real

Relay is a focused vertical slice built in a tight time-box. Knowing the limits of
what you've built matters as much as the build. Each cut below was deliberate, with a
clear production path.

| # | Deliberately simplified | Why it's fine here | How I'd do it in production |
|---|--------------------------|--------------------|------------------------------|
| 1 | **Schema via `create_all`**, no migrations | One-shot demo schema | **Alembic** migrations, shipped through the same merge → review → deploy pipeline as code |
| 2 | **Auth not wired** (Keycloak designed only, [ADR 0006](adr/0006-auth-boundary.md)) | Highest-risk-to-finish; design shows the understanding | OIDC token validation at the API edge; Auth Code + PKCE in the SPA; per-operator row scoping |
| 3 | **Cold path (data lake) sketched, not running** | Hot path is the demo's point | MinIO/Object Storage sink + Airflow rollups ([ADR 0001](adr/0001-hot-cold-data-split.md)) |
| 4 | **JSON events**, no schema registry | Readable, zero infra | Avro/Protobuf + Schema Registry; the `schema_version` field is the seam |
| 5 | **Dashboard polls every 3s** | Simple, robust, demo-proof | Server-Sent Events or WebSocket push for true real-time; polling is a fine default until it isn't |
| 6 | **Single-node** Postgres + Redpanda | Local demo | HA Postgres (replicas/failover), multi-broker Kafka with replication factor > 1 |
| 7 | **Poison messages logged + skipped** | Keeps the consumer alive | Dead-letter topic + alerting ([ADR 0003](adr/0003-event-driven-ingestion.md)) |
| 8 | **`VITE_API_BASE` baked at build** | Works for localhost demo | Runtime config injection (env-substituted at container start) |
| 9 | **Observability = structured logs + health probes** | Enough to see it working | Prometheus metrics + Grafana + OpenTelemetry tracing across producer→topic→consumer |
| 10 | **recharts bundle not code-split** (~530 kB) | Demo, not prod traffic | Lazy-load the chart, manual chunks |
| 11 | **Tests cover domain / API / idempotency** | Highest-value paths | + consumer integration tests, contract tests, a small load test for ingest |

The honest one-liner for the interview: **the ingestion pipeline runs end-to-end with
tests; the cluster/GitOps/auth layers are authored and reviewed, not a live production
deployment.** That distinction is the point — see the README "running vs scaffolded".
