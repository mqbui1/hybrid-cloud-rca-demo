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
for manifest in orchestrator flight-agent hotel-agent activity-agent currency-agent synthesizer; do
  kubectl apply -f "${REPO_DIR}/manifests/travel-planner/${manifest}.yaml"
done

# `kubectl apply`'s three-way merge only removes fields it previously tracked
# via the last-applied-config annotation. The inject scripts add these env
# vars with `kubectl set env` (bypassing that annotation), so `apply` alone
# can't strip them back out — unset them explicitly.
echo "==> Clearing any scenario-injected env vars..."
kubectl set env deployment/orchestrator -n "${NAMESPACE}" FLIGHT_AGENT_URL- 2>/dev/null || true
kubectl set env deployment/flight-agent -n "${NAMESPACE}" LB_UNHEALTHY- 2>/dev/null || true
kubectl set env deployment/currency-agent -n "${NAMESPACE}" CROSS_CLOUD_UNREACHABLE- 2>/dev/null || true

echo "==> Waiting for rollouts..."
for svc in orchestrator flight-agent hotel-agent activity-agent currency-agent synthesizer; do
  kubectl rollout status deployment/${svc} -n "${NAMESPACE}" --timeout=120s
  echo "    ${svc} restored"
done

echo "==> Disabling load generator until the next demo..."
kubectl patch cronjob travel-planner-loadgen -n "${NAMESPACE}" -p '{"spec":{"suspend":true}}'
kubectl delete jobs -n "${NAMESPACE}" --field-selector=status.successful=1 2>/dev/null || true

STATE_FILE="/tmp/hybrid-cloud-rca-demo-active-scenario"
if [ -f "${STATE_FILE}" ]; then
  # shellcheck disable=SC1090
  source "${STATE_FILE}"
  if [ -n "${HEC_URL:-}" ] && [ -n "${HEC_TOKEN:-}" ]; then
    echo "==> Sending resolution/heartbeat event for previous scenario (${SCENARIO})..."
    "${PYTHON3:-python3}" "${REPO_DIR}/synthetic-network-data/generate_events.py" \
      --scenario baseline --host "${HOST}" --device "${DEVICE}" || true
  else
    echo "==> Skipping network-event resolution (HEC_URL/HEC_TOKEN not set) —"
    echo "    the previous scenario's SolarWinds alert/ExtraHop detection will"
    echo "    remain 'active' in Splunk. Set HEC_URL/HEC_TOKEN before restoring"
    echo "    to auto-resolve it."
  fi
  rm -f "${STATE_FILE}"
fi

echo ""
echo "==> All services restored."
