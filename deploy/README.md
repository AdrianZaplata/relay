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
| `kind/` | Local Kubernetes overlay — the chart on a real cluster | **Yes — `deploy/kind/up.sh`** |
| `helm/relay/` | Helm packaging of the app services (prod + dev overlay) | **Yes — runs on kind**; prod path `helm lint`/`template`-validated |
| `argocd/` | ArgoCD `Application` — the GitOps glue | **Yes — reconciles kind** (`deploy/argocd/up.sh`) |
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
way to change production — and you can watch that loop happen on a local cluster below.

## Running it for real (on kind)

The whole loop runs end-to-end on a local [kind](https://kind.sigs.k8s.io) cluster.
The production chart deliberately ships **no** datastores (it expects managed PG Flex +
Strimzi), so a dev overlay — `values-dev.yaml`, gated by `devDatastores.enabled` —
adds an in-cluster Postgres + Redpanda to make the cluster self-contained. The app runs
from locally-built `:dev` images loaded straight into the kind node; nothing is pushed
to a registry.

```bash
# 1. Cluster + chart: create kind, build the 3 images, load them, helm install, seed.
bash deploy/kind/up.sh

# 2. See it: two port-forwards (web serves the SPA, api answers its calls).
kubectl -n relay port-forward svc/relay-web 8080:80 &
kubectl -n relay port-forward svc/relay-api  8000:80 &
open http://localhost:8080

# 3. GitOps: install ArgoCD and point it at this repo.
bash deploy/argocd/up.sh
```

### Demo the loop (merge → reconcile)

With ArgoCD watching the repo, git is the only way to change the cluster:

```bash
# edit deploy/helm/relay/values-dev.yaml: web.replicas 1 -> 2
git commit -am 'demo: scale web to 2' && git push
kubectl -n argocd annotate app relay argocd.argoproj.io/refresh=hard --overwrite
kubectl -n relay get pods -l app.kubernetes.io/name=relay-web -w   # a 2nd pod appears
```

Tear down with `kind delete cluster --name relay`.

### kind (dev) vs production

|  | kind (dev) | production |
|---|---|---|
| Datastores | in-cluster Postgres + Redpanda (`devDatastores.enabled`) | managed PG Flex + Strimzi |
| Images | bare `:dev`, loaded into the node | registry images, SHA-tagged by CI |
| Values | `values-dev.yaml` | `values.yaml` |
| ArgoCD `Application` | `relay-application-dev.yaml` | `relay-application.yaml` |
| HPA / Ingress | off (kind has no metrics-server / ingress controller) | on |

Same chart, same ArgoCD contract — only the values differ.
