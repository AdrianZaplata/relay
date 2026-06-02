#!/usr/bin/env bash
# Stand up Relay on a local kind cluster from the Helm chart.
#
#   create kind cluster -> build the 3 images -> load them into the node ->
#   helm install (dev values: in-cluster Postgres + Redpanda) -> seed demo data.
#
# Images are loaded straight into kind's container store and referenced by bare
# name with imagePullPolicy: IfNotPresent, so nothing is pushed to a registry.
# Idempotent: safe to re-run (reuses the cluster, rebuilds + reloads images, and rolls
# the app pods to pick them up). Run this BEFORE handing the cluster to ArgoCD
# (deploy/argocd/up.sh) — afterward ArgoCD's selfHeal owns the release, so re-running
# helm here would fight it.
set -euo pipefail

CLUSTER=relay
NAMESPACE=relay
CHART_TAG=dev
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> [1/6] kind cluster '${CLUSTER}'"
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER}"; then
  echo "    exists — reusing"
else
  kind create cluster --config "${ROOT}/deploy/kind/kind-config.yaml"
fi
kubectl config use-context "kind-${CLUSTER}" >/dev/null

echo "==> [2/6] build images (:${CHART_TAG})"
docker build -t "relay-service:${CHART_TAG}"   "${ROOT}/apps/relay"
docker build -t "relay-simulator:${CHART_TAG}" "${ROOT}/apps/simulator"
# The browser reaches the API on localhost:8000 (port-forward), same as compose.
docker build -t "relay-web:${CHART_TAG}" --build-arg VITE_API_BASE=http://localhost:8000 "${ROOT}/apps/web"

echo "==> [3/6] load images into kind"
kind load docker-image \
  "relay-service:${CHART_TAG}" "relay-web:${CHART_TAG}" "relay-simulator:${CHART_TAG}" \
  --name "${CLUSTER}"

echo "==> [4/6] helm upgrade --install"
helm upgrade --install "${CLUSTER}" "${ROOT}/deploy/helm/relay" \
  -f "${ROOT}/deploy/helm/relay/values-dev.yaml" \
  -n "${NAMESPACE}" --create-namespace

echo "==> [5/6] wait for datastores, create topic"
# 300s, not 180s: postgres:16-alpine + redpanda are pulled from upstream registries on
# a cold node (only the app :dev images are pre-loaded), which can be slow on first run.
kubectl -n "${NAMESPACE}" rollout status deploy/relay-postgres --timeout=300s
kubectl -n "${NAMESPACE}" rollout status deploy/relay-redpanda --timeout=300s
# Mirror the compose 'redpanda-init' one-shot: ensure the telemetry topic exists
# (auto-create is also on, this just removes the first-produce race). Idempotent.
kubectl -n "${NAMESPACE}" exec deploy/relay-redpanda -- \
  rpk topic create telemetry --partitions 3 --replicas 1 2>/dev/null || true
# Restart all app pods now that the broker + topic exist: (1) ingestor/simulator may
# have crash-looped while the broker came up, and (2) on a re-run the :dev tag is
# unchanged, so without a restart api/web would keep running the previous image instead
# of the one we just rebuilt + loaded.
kubectl -n "${NAMESPACE}" rollout restart \
  deploy/relay-api deploy/relay-ingestor deploy/relay-web deploy/relay-simulator

echo "==> [6/6] wait for app, seed demo fleet"
kubectl -n "${NAMESPACE}" rollout status deploy/relay-api --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/relay-ingestor --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/relay-web --timeout=180s
# Seed the demo fleet so the simulator has active assets to report on. The seed is
# idempotent (no-op if assets already exist), so re-running up.sh is safe.
kubectl -n "${NAMESPACE}" exec deploy/relay-api -- python -m relay.seed

cat <<EOF

Relay is up on kind (namespace: ${NAMESPACE}).

  kubectl -n ${NAMESPACE} get pods

Open the dashboard (two port-forwards — web serves the SPA, api answers its calls):

  kubectl -n ${NAMESPACE} port-forward svc/relay-web 8080:80 &
  kubectl -n ${NAMESPACE} port-forward svc/relay-api 8000:80 &
  open http://localhost:8080

Then layer on GitOps:  bash ${ROOT}/deploy/argocd/up.sh
Tear it all down:      kind delete cluster --name ${CLUSTER}
EOF
