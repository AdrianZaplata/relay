# Relay

A miniature **real-time telemetry platform** for B2B operators — built as a focused,
end-to-end vertical slice of a greenfield, cloud-native operator platform.

Connected **assets** in the field emit telemetry → events flow through **Kafka** →
an **ingestor** writes them to **PostgreSQL** (hot operational state) → a **FastAPI**
service serves a **React/TypeScript** operator dashboard.

> Relay deliberately mirrors a production operator-platform architecture (event-driven
> ingestion, hot/cold data split, GitOps delivery) at small scale, so every design
> decision is one I made and can defend — not a tool I merely touched.

---

## Architecture

```
  ┌───────────────┐   produce    ┌──────────────┐   consume   ┌────────────────┐
  │  simulator    │ ───────────► │  Kafka topic │ ──────────► │   ingestor     │
  │ (asset fleet) │  keyed by    │ "telemetry"  │  consumer   │ (idempotent    │
  │  producer     │  asset_id    │  (Redpanda)  │  group      │  upsert)       │
  └───────────────┘              └──────────────┘             └───────┬────────┘
                                                                      │ write
                                                                      ▼
  ┌───────────────┐    REST/JSON      ┌──────────────┐        ┌────────────────┐
  │  web (React)  │ ◄──────────────►  │   api        │ ◄────► │  PostgreSQL    │
  │  operator     │   query + cmd     │  (FastAPI)   │  query │  hot operational│
  │  dashboard    │                   │              │        │  state          │
  └───────────────┘                   └──────────────┘        └────────────────┘

  Hot path:  telemetry + current asset state the dashboard needs *now*  → PostgreSQL
  Cold path: cheap, high-volume raw history → object-storage data lake → rollups
             (Airflow in production). Sketched here; see docs/adr/0001.
```

`api` and `ingestor` are the **same codebase deployed as two services** — they share
the domain model but scale independently (read traffic vs ingest throughput). This is
the event-driven, loosely-coupled core the platform is built around.

---

## Quickstart

```bash
make demo     # build, start the whole stack, seed demo assets — dashboard on :5173
make test     # run the backend test suite (state machine, API, idempotency)
make logs     # tail all services
make down     # stop everything
```

Then open **http://localhost:5173** — create an asset, drive it through its lifecycle
(watch an illegal transition get rejected with `409`), and see live telemetry stream
into the chart **without anyone calling an HTTP endpoint** — it arrives via Kafka.

---

## What this demonstrates (mapped to the platform stack)

| Area | Here | Production equivalent |
|------|------|----------------------|
| Backend API | FastAPI + async SQLAlchemy | Python/FastAPI services |
| Data model | PostgreSQL, lifecycle state machine, audit log | PostgreSQL Flex |
| Event-driven | Redpanda (Kafka API), producer/consumer groups | Apache Kafka (Strimzi) |
| Frontend | React + TypeScript + Vite | React/TS operator apps |
| Hot/cold data | PG hot state + object-storage lake sketch | PG Flex + Object Storage + Airflow |
| Delivery | Dockerized, Helm chart, ArgoCD `Application` | K8s (SKE) + Helm + ArgoCD GitOps |
| IaC | STACKIT-targeted Terraform (authored) | Terraform/Terragrunt |
| Auth | OIDC boundary (documented) | Keycloak |

See [`docs/adr/`](docs/adr/) for the decisions behind each — context, tradeoff, and
what I'd do differently at production scale.

---

## Repository layout

```
relay/
  apps/
    relay/        # shared Python package: domain, models, db, FastAPI api, ingestor
    simulator/    # device-fleet telemetry producer
    web/          # React + TypeScript operator dashboard
  deploy/
    compose/      # docker-compose (local dev + demo)
    helm/         # Helm chart (K8s packaging)
    argocd/       # ArgoCD Application (GitOps)
    terraform/    # STACKIT infrastructure as code (authored)
  docs/adr/       # architecture decision records
```

---

## Status: running vs scaffolded

Honest accounting (this matters more than breadth):

- **Running end-to-end:** simulator → Kafka → ingestor → PostgreSQL → API → dashboard,
  with tests and a one-command demo.
- **Authored & reviewed (not a live cluster):** Helm chart, ArgoCD `Application`,
  STACKIT Terraform, CI pipeline. I can walk through each and explain the GitOps loop.

See [`docs/TRADEOFFS.md`](docs/TRADEOFFS.md) for what I deliberately left out and how
I'd build it for real.
