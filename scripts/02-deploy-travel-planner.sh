#!/bin/bash
# ============================================================
# Step 2: Build and deploy Travel Planner microservices
# ============================================================
# Required env vars:
#   LLM_PROVIDER    - "openai", "bedrock", or "mock" (default: mock)
#   OPENAI_API_KEY  - required if LLM_PROVIDER=openai
#   OPENAI_MODEL    - optional (default: gpt-4o-mini)
#   OPENAI_BASE_URL - optional override for OpenAI-compatible endpoints
#   BEDROCK_MODEL_ID - optional (default: anthropic.claude-3-5-haiku-20241022-v1:0)
#   AWS_DEFAULT_REGION - optional (default: us-east-1)
#   K3D_CLUSTER     - k3d cluster name (default: k3s-default)
#
# Pre-set on demo instances: ACCESS_TOKEN, REALM, INSTANCE
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LLM_PROVIDER="${LLM_PROVIDER:-mock}"
K3D_CLUSTER="${K3D_CLUSTER:-${CLUSTER_NAME:-k3s-default}}"

echo "==> Building travel-planner Docker image..."
docker build -t travel-planner:latest "${REPO_DIR}/travel-planner"

echo "==> Importing image into k3d cluster '${K3D_CLUSTER}'..."
k3d image import travel-planner:latest -c "${K3D_CLUSTER}"

echo "==> Creating travel-planner namespace..."
kubectl apply -f "${REPO_DIR}/manifests/travel-planner/namespace.yaml"

echo "==> Creating llm-secret (LLM_PROVIDER=${LLM_PROVIDER})..."
kubectl create secret generic llm-secret \
  --namespace travel-planner \
  --from-literal=provider="${LLM_PROVIDER}" \
  --from-literal=api_key="${OPENAI_API_KEY:-none}" \
  --from-literal=base_url="${OPENAI_BASE_URL:-}" \
  --from-literal=model="${OPENAI_MODEL:-gpt-4o-mini}" \
  --from-literal=bedrock_model_id="${BEDROCK_MODEL_ID:-anthropic.claude-3-5-haiku-20241022-v1:0}" \
  --from-literal=aws_region="${AWS_DEFAULT_REGION:-us-east-1}" \
  --from-literal=mock_mode="$([ "${LLM_PROVIDER}" = "mock" ] && echo true || echo false)" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Copying demo-secret to travel-planner namespace..."
kubectl get secret demo-secret -n default -o yaml \
  | sed 's/namespace: default/namespace: travel-planner/' \
  | kubectl apply -f - 2>/dev/null || true

# If demo-secret doesn't exist (local dev), create a placeholder
kubectl create secret generic demo-secret \
  --namespace travel-planner \
  --from-literal=env="${INSTANCE:-travel-planner-demo}-demo" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Deploying travel-planner services..."
for manifest in orchestrator flight-agent hotel-agent activity-agent synthesizer; do
  kubectl apply -f "${REPO_DIR}/manifests/travel-planner/${manifest}.yaml"
done

echo "==> Waiting for services to be ready..."
for svc in orchestrator flight-agent hotel-agent activity-agent synthesizer; do
  kubectl rollout status deployment/${svc} -n travel-planner --timeout=180s
  echo "    ${svc} ready"
done

echo "==> Deploying load generator..."
kubectl apply -f "${REPO_DIR}/manifests/travel-planner/loadgen.yaml"

echo ""
echo "==> Travel planner deployed successfully."
echo "    Test it: kubectl run -it --rm test --image=curlimages/curl --restart=Never -n travel-planner -- \\"
echo "      curl -X POST http://orchestrator.travel-planner.svc.cluster.local:8080/plan \\"
echo "        -H 'Content-Type: application/json' \\"
echo "        -d '{\"origin\": \"Seattle\", \"destination\": \"Paris\", \"travellers\": 2}'"
