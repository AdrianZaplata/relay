# Delivery

How Relay goes from a git commit to running pods, the GitOps way.

```
  developer ──merge MR──▶ GitLab CI ──build+push image (SHA tag)──▶ registry
                              │
                              ▼  bump image.tag in deploy/helm/relay (git)
                         git (source of truth)
                              │  ArgoCD watches this path
                              ▼
                          ArgoCD ──sync──▶ Kubernetes (SKE): api · ingestor · web
```

| Path | What it is | Runs? |
|---|---|---|
| `compose/` | Local dev + demo (Postgres + Redpanda + all services) | **Yes — `make demo`** |
| `helm/relay/` | Production packaging of the app services | Authored + `helm lint`/`template` validated |
| `argocd/` | ArgoCD `Application` — the GitOps glue | Authored |
| `terraform/` | STACKIT infra (SKE, PG Flex, Object Storage, Secrets Manager) | Authored |

## Separation of concerns

- **Terraform** provisions infrastructure (the cluster + managed data services).
- **Helm + ArgoCD** deliver the application onto that cluster.
- **PostgreSQL Flex** (Terraform) and **Kafka/Strimzi** are *not* in the Helm chart —
  the chart deploys stateless app services only and points at managed endpoints.

## The reconciliation loop (what ArgoCD actually does)

ArgoCD continuously compares the live cluster against the desired state declared in
git (`deploy/helm/relay`). On drift — a new image tag from CI, an edited replica count,
or someone hand-editing a Deployment — it syncs the cluster back to git. `selfHeal`
reverts manual changes; `prune` deletes resources removed from git. Git is the only
way to change production.

## Running it for real (not done in this build)

```bash
kind create cluster
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f deploy/argocd/relay-application.yaml
# then: edit deploy/helm/relay/values.yaml in git, push, watch ArgoCD sync.
```
