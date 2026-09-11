#!/bin/bash
# ============================================================
# Restore all travel-planner services to their declared manifest state
# ============================================================
# Reverses any failure injection (e.g. scripts/03-inject-dns-failure.sh) by
# re-applying the manifests, which resets env vars and replica counts back
# to their committed values.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="travel-planner"

echo "==> Restoring travel-planner services to manifest state..."
for manifest in orchestrator flight-agent hotel-agent activity-agent synthesizer; do
  kubectl apply -f "${REPO_DIR}/manifests/travel-planner/${manifest}.yaml"
done

echo "==> Waiting for rollouts..."
for svc in orchestrator flight-agent hotel-agent activity-agent synthesizer; do
  kubectl rollout status deployment/${svc} -n "${NAMESPACE}" --timeout=120s
  echo "    ${svc} restored"
done

echo ""
echo "==> All services restored."
