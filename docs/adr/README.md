# Architecture Decision Records

Short records of the decisions behind Relay — each with context, the decision, the
trade-off, and what I'd do differently at production scale. These are the "why",
the code is the "what".

| # | Decision | One-line rationale |
|---|----------|--------------------|
| [0001](0001-hot-cold-data-split.md) | Hot/cold data split | PostgreSQL for current state, object-storage lake for raw history |
| [0002](0002-telemetry-table-shape.md) | Narrow/long telemetry table | Adding a metric is data, not a migration |
| [0003](0003-event-driven-ingestion.md) | Event-driven ingestion via Kafka | Decouple + scale ingest independently; at-least-once + idempotent |
| [0004](0004-lifecycle-state-machine.md) | Lifecycle as an audited state machine | One pure, testable rule; illegal moves are 409 |
| [0005](0005-api-design.md) | REST API design | Resource + command sub-resources; codes carry meaning |
| [0006](0006-auth-boundary.md) | Auth boundary (Keycloak/OIDC) | Token validation at the edge; designed, not fully built |
