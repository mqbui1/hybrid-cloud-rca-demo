#!/bin/bash
# ============================================================
# Scenario: cross-cloud connectivity failure (AWS -> Azure hop)
# ============================================================
# Simulates a broken network path between two cloud providers (e.g. VPC
# peering / ExpressRoute / Transit Gateway route down): currency-agent is
# tagged cloud.provider=azure while the rest of the app is tagged
# cloud.provider=aws (see manifests/travel-planner/currency-agent.yaml and
# orchestrator.yaml). Unlike the DNS scenario (immediate resolution error)
# or the LB scenario (immediate clean 503), a dropped cross-cloud route
# produces no response at all — the request just hangs until the caller's
# own timeout fires, which is what a real routing/peering failure looks
# like from the caller's side.
#
# Usage: bash scripts/06-inject-multicloud-failure.sh
# Restore with: bash scripts/04-restore-services.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAMESPACE="travel-planner"

echo "==> Resetting to a clean baseline (undoing any previously active scenario)..."
bash "${SCRIPT_DIR}/04-restore-services.sh"

echo "==> Marking currency-agent unreachable (simulated cross-cloud route failure)..."
kubectl set env deployment/currency-agent -n "${NAMESPACE}" CROSS_CLOUD_UNREACHABLE=true

echo "==> Waiting for currency-agent rollout..."
kubectl rollout status deployment/currency-agent -n "${NAMESPACE}" --timeout=60s

echo "==> Enabling load generator for the duration of this demo..."
kubectl patch cronjob travel-planner-loadgen -n "${NAMESPACE}" -p '{"spec":{"suspend":false}}'

echo "==> Firing a test request to generate a failing trace (this will hang ~5s before the orchestrator's timeout fires)..."
kubectl run -it --rm multicloud-failure-test --image=curlimages/curl --restart=Never -n "${NAMESPACE}" -- \
  curl -s -X POST http://orchestrator.travel-planner.svc.cluster.local:8080/plan \
    -H 'Content-Type: application/json' \
    -d '{"origin": "Seattle", "destination": "Paris", "travellers": 2}' \
  || true

HOST=$(kubectl get pod -n "${NAMESPACE}" -l app=currency-agent -o jsonpath='{.items[0].spec.nodeName}')
cat > /tmp/hybrid-cloud-rca-demo-active-scenario <<EOF
SCENARIO=multicloud-failure
DEVICE=aws-azure-vnet-peering-01
HOST=${HOST}
EOF

echo ""
echo "==> Multi-cloud failure injected."
echo "    Expect: agent.call.currency-agent span times out after ~5s (the"
echo "    orchestrator's per-call timeout), while orchestrator health checks"
echo "    and every other agent (all tagged cloud.provider=aws) stay healthy."
echo "    Look at cloud.provider/cloud.region resource attributes on the"
echo "    currency-agent span vs. every other span to show the cross-cloud hop."
echo "    Correlating host: ${HOST}"
echo "    Restore with: bash scripts/04-restore-services.sh"
