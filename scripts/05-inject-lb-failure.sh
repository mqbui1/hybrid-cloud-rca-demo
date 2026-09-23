#!/bin/bash
# ============================================================
# Scenario: load-balancer target-unhealthy failure on the cloud-side hop
# ============================================================
# Simulates flight-agent being marked unhealthy by its load balancer (failing
# health checks, removed from rotation): the pod itself is up and DNS
# resolves fine, but every request returns HTTP 503. This is deliberately a
# different failure signature from the DNS scenario (connection resolution
# failure) — here the app layer sees a clean HTTP error from a reachable
# service, matching what a real "0 of N targets healthy" ALB/ELB event looks
# like from the caller's side.
#
# Usage: bash scripts/05-inject-lb-failure.sh
# Restore with: bash scripts/04-restore-services.sh
# ============================================================

set -e

NAMESPACE="travel-planner"

echo "==> Marking flight-agent unhealthy (simulated LB health-check failure)..."
kubectl set env deployment/flight-agent -n "${NAMESPACE}" LB_UNHEALTHY=true

echo "==> Waiting for flight-agent rollout..."
kubectl rollout status deployment/flight-agent -n "${NAMESPACE}" --timeout=60s

echo "==> Firing a test request to generate a failing trace..."
kubectl run -it --rm lb-failure-test --image=curlimages/curl --restart=Never -n "${NAMESPACE}" -- \
  curl -s -X POST http://orchestrator.travel-planner.svc.cluster.local:8080/plan \
    -H 'Content-Type: application/json' \
    -d '{"origin": "Seattle", "destination": "Paris", "travellers": 2}' \
  || true

echo ""
echo "==> LB failure injected."
echo "    Expect: agent.call.flight-agent span errors with an HTTP 503"
echo "    (Service Temporarily Unavailable), while orchestrator health checks"
echo "    and every other agent stay healthy."
echo "    Restore with: bash scripts/04-restore-services.sh"
