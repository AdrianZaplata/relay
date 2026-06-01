# Relay

A miniature **real-time telemetry platform** for a connected **e-bike fleet** — built
as a focused, end-to-end vertical slice of a greenfield, cloud-native micromobility
platform.

Connected pedelecs in the field emit telemetry → events flow through **Kafka** → an
**ingestor** writes them to **PostgreSQL** (hot operational state) → a **FastAPI**
service serves a **React/TypeScript** operator console.

> Relay deliberately mirrors a production fleet-telemetry architecture — event-driven
> ingestion, a hot/cold data split, GitOps delivery — at small scale, so every design
> decision is one I made and can defend. See [`docs/adr/`](docs/adr/).

---

## Architecture

```
  ┌───────────────┐   produce    ┌──────────────┐   consume   ┌────────────────┐
  │  simulator    │ ───────────► │  Kafka topic │ ──────────► │   ingestor     │
  │ (e-bike fleet)│  key=        │ "telemetry"  │  consumer   │ (idempotent    │
  │  producer     │  asset_id    │ 3 partitions │  group      │  upsert)       │
  └───────────────┘              └──────────────┘             └───────┬────────┘
                                                                      │ write
                                                                      ▼
  ┌───────────────┐    REST/JSON      ┌──────────────┐        ┌────────────────┐
  │  web (React)  │ ◄──────────────►  │   api        │ ◄────► │  PostgreSQL    │
  │  operator     │   query + cmd     │  (FastAPI)   │  query │  hot operational│
  │  console      │                   │              │        │  state          │
  └───────────────┘                   └──────────────┘        └────────────────┘

  Hot path:  current bike state + recent telemetry the console needs now → PostgreSQL
  Cold path: cheap, high-volume raw history → object-storage data lake → rollups
             (Airflow in production). Sketched here; see docs/adr/0001.
```

`api` and `ingestor` are the **same codebase deployed as two services** — they share
the domain model but scale independently (read traffic vs ingest throughput). Telemetry
is keyed by `asset_id`, so every bike's readings keep per-asset order on one partition.

---

## Quickstart

```bash
make demo     # build, start the whole stack, seed a demo fleet — console on :5173
make test     # backend test suite (state machine, API contract, idempotency)
make logs     # tail all services
make down     # stop everything
```

Then open **http://localhost:5173** — create a bike, drive it through its lifecycle
(watch an illegal transition get rejected with `409`), and see live telemetry stream
into the chart **without anyone calling an HTTP endpoint** — it arrives via Kafka.
OpenAPI docs at **http://localhost:8000/docs**.

---

## What this demonstrates (mapped to a cloud-native micromobility stack)

| Area | Here | Production equivalent |
|------|------|----------------------|
| Backend API | FastAPI + async SQLAlchemy (asyncpg) | Python/FastAPI services |
| Data model | PostgreSQL, lifecycle state machine, audit log | PostgreSQL Flex |
| Event-driven | Redpanda (Kafka API), producer + consumer group | Apache Kafka (Strimzi) |
| Frontend | React + TypeScript + Vite | React/TS operator apps |
| Hot/cold data | PG hot state + object-storage lake sketch | PG Flex + Object Storage + Airflow |
| Delivery | Dockerized, Helm chart, ArgoCD `Application` | Kubernetes + Helm + ArgoCD GitOps |
| IaC | STACKIT-targeted Terraform (authored) | Terraform / Terragrunt |
| Auth | OIDC boundary (designed, [adr/0006](docs/adr/0006-auth-boundary.md)) | Keycloak |

Decisions — context, trade-off, and what I'd do at scale — live in
[`docs/adr/`](docs/adr/). What I deliberately cut is in [`docs/TRADEOFFS.md`](docs/TRADEOFFS.md).

---

## Repository layout

```
relay/
  apps/
    relay/        # shared Python package: domain, models, db, FastAPI api, ingestor
    simulator/    # e-bike fleet telemetry producer
    web/          # React + TypeScript operator console
  deploy/
    compose/      # docker-compose (local dev + demo)
    helm/         # Helm chart (K8s packaging)
    argocd/       # ArgoCD Application (GitOps)
    terraform/    # STACKIT infrastructure as code (authored)
  docs/adr/       # architecture decision records
```

## Configuration

Services read `RELAY_*` environment variables (compose sets them):

| Variable | Default | Purpose |
|---|---|---|
| `RELAY_DATABASE_URL` | `postgresql+asyncpg://relay:relay@localhost:5432/relay` | async Postgres URL |
| `RELAY_KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` | Kafka/Redpanda brokers |
| `RELAY_TELEMETRY_TOPIC` | `telemetry` | telemetry topic |
| `RELAY_CONSUMER_GROUP` | `relay-ingestor` | ingestor consumer group |
| `RELAY_LOG_LEVEL` | `INFO` | log level |

---

## Status: running vs scaffolded

Honest accounting (this matters more than breadth):

- **Running end-to-end:** simulator → Kafka → ingestor → PostgreSQL → API → console,
  with tests and a one-command demo.
- **Authored & reviewed (not a live cluster):** Helm chart, ArgoCD `Application`,
  STACKIT Terraform, GitLab CI. Each is something I can walk through and explain.

See [`docs/TRADEOFFS.md`](docs/TRADEOFFS.md) for the full list and the production path.
