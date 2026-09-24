#!/bin/bash
# ============================================================
# Scenario: DNS resolution failure on an on-prem-to-cloud hop
# ============================================================
# Simulates a broken on-prem DNS resolver/relay: the orchestrator's flight-agent
# is healthy and reachable, but the orchestrator can no longer resolve the
# hostname it needs to reach it — the failure is at the network/DNS layer, not
# the application layer. This is deliberately a different failure signature
# from "service down" (connection refused): it's a DNS resolution error
# (e.g. "Failed to resolve ... Name or service not known").
#
# Usage: bash scripts/03-inject-dns-failure.sh
# Restore with: bash scripts/04-restore-services.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAMESPACE="travel-planner"
BAD_HOSTNAME="flight-agent.onprem-dns-relay.invalid"

echo "==> Resetting to a clean baseline (undoing any previously active scenario)..."
bash "${SCRIPT_DIR}/04-restore-services.sh"

echo "==> Breaking DNS resolution for the orchestrator -> flight-agent hop..."
kubectl set env deployment/orchestrator -n "${NAMESPACE}" \
  FLIGHT_AGENT_URL="http://${BAD_HOSTNAME}:8080"

echo "==> Waiting for orchestrator rollout..."
kubectl rollout status deployment/orchestrator -n "${NAMESPACE}" --timeout=60s

echo "==> Enabling load generator for the duration of this demo..."
kubectl patch cronjob travel-planner-loadgen -n "${NAMESPACE}" -p '{"spec":{"suspend":false}}'

echo "==> Firing a test request to generate a failing trace..."
kubectl run -it --rm dns-failure-test --image=curlimages/curl --restart=Never -n "${NAMESPACE}" -- \
  curl -s -X POST http://orchestrator.travel-planner.svc.cluster.local:8080/plan \
    -H 'Content-Type: application/json' \
    -d '{"origin": "Seattle", "destination": "Paris", "travellers": 2}' \
  || true

HOST=$(kubectl get pod -n "${NAMESPACE}" -l app=flight-agent -o jsonpath='{.items[0].spec.nodeName}')
cat > /tmp/hybrid-cloud-rca-demo-active-scenario <<EOF
SCENARIO=dns-failure
DEVICE=onprem-dns-relay-01
HOST=${HOST}
EOF

echo ""
echo "==> DNS failure injected."
echo "    Expect: agent.call.flight-agent span errors with a DNS resolution"
echo "    failure (hostname: ${BAD_HOSTNAME}), while orchestrator health checks"
echo "    and every other agent stay healthy."
echo "    Correlating host: ${HOST}"
echo "    Restore with: bash scripts/04-restore-services.sh"
