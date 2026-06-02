#!/usr/bin/env bash
# Install ArgoCD into the kind cluster and point it at this repo, so the cluster
# is reconciled from git instead of from `helm install`. Run AFTER deploy/kind/up.sh.
#
# ArgoCD pulls the Helm chart from GitHub; the :dev images it references still come
# from kind's local store (loaded by up.sh), not a registry. The Application is
# applied with targetRevision = your current branch, so `git push` -> ArgoCD sync
# works whether you're on a feature branch or on main.
set -euo pipefail

CLUSTER=relay
ARGOCD_NS=argocd
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARGOCD_MANIFEST="https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"

kubectl config use-context "kind-${CLUSTER}" >/dev/null

echo "==> [1/4] install ArgoCD"
kubectl create namespace "${ARGOCD_NS}" --dry-run=client -o yaml | kubectl apply -f -
# server-side apply: the ApplicationSet CRD's schema exceeds the 256KB limit that
# client-side apply would try to stash in the last-applied-configuration annotation.
kubectl apply --server-side --force-conflicts -n "${ARGOCD_NS}" -f "${ARGOCD_MANIFEST}"

echo "==> [2/4] wait for ArgoCD to be ready (this pulls a few images)"
kubectl -n "${ARGOCD_NS}" rollout status deploy/argocd-repo-server --timeout=300s
kubectl -n "${ARGOCD_NS}" rollout status deploy/argocd-server --timeout=300s
kubectl -n "${ARGOCD_NS}" rollout status statefulset/argocd-application-controller --timeout=300s

echo "==> [3/4] apply the Relay Application (tracking this branch)"
REV="$(git -C "${ROOT}" rev-parse --abbrev-ref HEAD)"
[ "${REV}" = "HEAD" ] && REV=main # detached checkout -> fall back to main
if ! git -C "${ROOT}" ls-remote --exit-code --heads origin "${REV}" >/dev/null 2>&1; then
  echo "    WARNING: branch '${REV}' is not on origin yet — push it or ArgoCD can't see it."
fi
# Escape sed-special chars (& | \) so unusual branch names don't corrupt the rewrite.
REV_SED="$(printf '%s' "${REV}" | sed 's/[&|\\]/\\&/g')"
sed "s|targetRevision: main|targetRevision: ${REV_SED}|" \
  "${ROOT}/deploy/argocd/relay-application-dev.yaml" | kubectl apply -f -
echo "    Application 'relay-dev' is tracking origin/${REV}"

echo "==> [4/4] wait for first sync"
sync="" health=""
for _ in $(seq 1 40); do
  sync="$(kubectl -n "${ARGOCD_NS}" get app relay-dev -o jsonpath='{.status.sync.status}' 2>/dev/null || true)"
  health="$(kubectl -n "${ARGOCD_NS}" get app relay-dev -o jsonpath='{.status.health.status}' 2>/dev/null || true)"
  echo "    sync=${sync:-?} health=${health:-?}"
  [ "${sync}" = "Synced" ] && [ "${health}" = "Healthy" ] && break
  sleep 5
done

if [ "${sync}" != "Synced" ] || [ "${health}" != "Healthy" ]; then
  echo "ERROR: ArgoCD app 'relay-dev' never reached Synced/Healthy (sync=${sync:-?} health=${health:-?})." >&2
  echo "       Common causes: branch not pushed to origin, repo unreachable, or :dev images not loaded into kind." >&2
  echo "Diagnostics:" >&2
  kubectl -n "${ARGOCD_NS}" get app relay-dev -o wide >&2 || true
  kubectl -n "${ARGOCD_NS}" get app relay-dev \
    -o jsonpath='{range .status.conditions[*]}{"  "}{.type}: {.message}{"\n"}{end}' >&2 || true
  exit 1
fi

ADMIN_PW="$(kubectl -n "${ARGOCD_NS}" get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || true)"
cat <<EOF

ArgoCD is installed and managing the 'relay-dev' Application.

Open the ArgoCD UI:

  kubectl -n ${ARGOCD_NS} port-forward svc/argocd-server 8083:443 &
  open https://localhost:8083      # user: admin   pass: ${ADMIN_PW:-<see below>}

  # password (if blank above):
  kubectl -n ${ARGOCD_NS} get secret argocd-initial-admin-secret \\
    -o jsonpath='{.data.password}' | base64 -d; echo

Demo the GitOps loop:

  1. Edit deploy/helm/relay/values-dev.yaml: web.replicas 1 -> 2
  2. git commit -am 'demo: scale web to 2' && git push
  3. Force an immediate refresh (or wait ~3m for the poll):
       kubectl -n ${ARGOCD_NS} annotate app relay-dev argocd.argoproj.io/refresh=hard --overwrite
  4. Watch the new replica appear:
       kubectl -n relay get pods -l app.kubernetes.io/name=relay-web -w
EOF
