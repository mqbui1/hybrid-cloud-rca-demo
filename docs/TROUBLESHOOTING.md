# Troubleshooting / deployment lessons learned

Issues hit while standing this demo up, and how to avoid or fix them, so a fresh deploy on
someone else's laptop goes smoothly.

## `kubectl`/`helm` "TLS handshake timeout" against the k3d API server
**Symptom:** intermittent or persistent `Unable to connect to the server: net/http: TLS handshake
timeout` from `kubectl`, `helm`, or the inject/restore scripts, sometimes escalating to the node
flapping `NotReady` or the k3d server container's CPU pegged at 200%+.

**Root cause:** Docker Desktop's VM has a fixed CPU/memory cap. If any *other* container workload
(another k3d/kind cluster, another docker-compose demo stack, etc.) is running at the same time,
it competes for the same capped VM resources as this cluster's control plane. k3s's default
datastore (`kine` over SQLite) degrades badly under CPU starvation — once it falls behind, retries
alone don't help.

**Fix:**
1. Check for contention first: `docker stats --no-stream` — if you see containers you don't
   recognize (i.e. not `k3d-hybrid-cloud-rca-demo-*`) burning significant CPU/mem, that's almost
   always the actual cause, not this demo's own workload.
2. Pause/stop the other workload, or run this demo at a time when nothing else is using Docker
   Desktop.
3. If the control plane is *already* badly degraded (queries taking multiple seconds, timeouts
   climbing past 30–60s), don't try to wait it out — delete and recreate the cluster
   (`k3d cluster delete hybrid-cloud-rca-demo && k3d cluster create hybrid-cloud-rca-demo`) and
   re-run the setup scripts below. It's faster than troubleshooting a wedged `kine`/SQLite store.

## `helm repo update` fails with a wall of `401` errors
**Symptom:** `helm repo update` (no repo name argument) errors out on repos you never added
yourself, e.g. `helm-fluent-remote`, `helm-bitnami-remote`, etc., with `401` from an internal
Artifactory mirror.

**Root cause:** `helm repo update` with no arguments refreshes *every* repo in your local Helm
config, not just the one this project needs. If your machine has other (e.g. corporate-internal)
Helm repos configured globally with expired/invalid credentials, the whole command fails even
though the one repo this demo actually needs (`splunk-otel-collector-chart`) updated fine.

**Fix:** scope the update to just the repo this demo needs:
```bash
helm repo update splunk-otel-collector-chart
```
(The same class of issue can hit `uv`/`pip` if a global package-index config has an expired
token set as the default index — mark such indexes `explicit = true` in `uv.toml` so tooling
falls back to public PyPI instead of failing closed.)

## First `01-install-otel-collector.sh` run fails on the `Instrumentation` webhook
**Symptom:** first-time install errors with either:
- `no endpoints available for service "splunk-otel-collector-operator-webhook"`, or
- `tls: failed to verify certificate: x509: certificate signed by unknown authority` —
  **and this error persists even after retrying the exact same `helm upgrade --install` command
  multiple times.**

**Root cause:** the chart's operator sub-chart has a `pre-install,pre-upgrade` Helm hook
(`helm.sh/hook-delete-policy: before-hook-creation`) that deletes and regenerates the operator's
self-signed webhook TLS cert secret **on every single `helm install`/`helm upgrade` run**, before
the rest of the chart's resources (including the `Instrumentation` CR, which is
admission-webhook-validated) get applied in that same run. The already-running operator pod only
picks up a freshly-written cert on its own poll cycle (~10s) plus however long kubelet takes to
sync the updated Secret into the pod's mounted volume (up to ~60–90s) — so the `Instrumentation`
CR apply, happening seconds after the hook wrote a *brand new* cert, almost always loses that race
and gets rejected by a webhook still serving the *previous* cert. Because every retry re-runs the
hook and mints yet another new cert, blindly re-running the same `helm upgrade --install` command
repeats the identical failure rather than resolving it.

**Fix:** don't just retry `helm upgrade --install`. Instead, let the cert settle, then apply only
the missing resource directly:
```bash
# 1. Confirm the operator pod is up and stable (not mid-restart):
kubectl get pods -l app.kubernetes.io/name=operator

# 2. Wait for the cert to fully propagate to the running pod (kubelet secret-volume sync lag):
sleep 90

# 3. Apply just the Instrumentation CR that failed, without re-triggering the cert-regen hook:
helm get manifest splunk-otel-collector | \
  awk '/kind: Instrumentation/{f=1} f' > /tmp/instrumentation.yaml
kubectl apply -f /tmp/instrumentation.yaml
```
The Helm release may still show `STATUS: failed` in `helm status`/`helm history` afterward — that
is cosmetic bookkeeping; what matters is `kubectl get pods` shows the agent DaemonSet, cluster
receiver, and operator all `Running`, and the `Instrumentation` CR exists
(`kubectl get instrumentation`).

## `K3D_CLUSTER` env var default doesn't match this repo's cluster name
`scripts/02-deploy-travel-planner.sh` defaults `K3D_CLUSTER` to `k3s-default`. This repo's
cluster is named `hybrid-cloud-rca-demo`, so **always set it explicitly**:
```bash
K3D_CLUSTER=hybrid-cloud-rca-demo bash scripts/02-deploy-travel-planner.sh
```

## `generate_events.py` / HEC exporter fails with `{"text":"Invalid token","code":4}` (403)
**Symptom:** `synthetic-network-data/generate_events.py` fails with a `403` and
`{"text":"Invalid token","code":4}`, and/or the OTel Collector agent's logs show the
`splunk_hec/platform_logs` exporter dropping data with the same error.

**Root cause:** the HEC token baked into the `splunk-otel-collector` k8s secret (set via
`HEC_TOKEN` when `scripts/01-install-otel-collector.sh` was run) doesn't exist on the Splunk
Platform stack — most likely because the stack is fresh and no HEC token was ever created on it.
Confirm with the stack's management API (port 8089, requires stack admin credentials):
```bash
curl -k -u admin:<password> \
  "https://<stack-host>:8089/servicesNS/nobody/search/data/inputs/http?output_mode=json"
```
If `"entry":[]`, no tokens exist at all.

**Fix:** create one via the same management API, scoped to the index this demo uses:
```bash
curl -k -u admin:<password> \
  "https://<stack-host>:8089/servicesNS/nobody/splunk_httpinput/data/inputs/http" \
  -d "name=hybrid-cloud-rca-demo-hec" \
  -d "index=hybrid-cloud-rca-demo" \
  -d "indexes=hybrid-cloud-rca-demo" \
  -d "disabled=0"
```
The response's `content.token` field is the new HEC token. Patch it into the running cluster and
restart the agent to pick it up (env vars from secrets don't hot-reload):
```bash
kubectl get secret splunk-otel-collector -n default -o json | python3 -c "
import json,sys,base64
d=json.load(sys.stdin)
d['data']['splunk_platform_hec_token']=base64.b64encode(b'<new-token>').decode()
print(json.dumps(d))
" | kubectl apply -f -
kubectl rollout restart daemonset/splunk-otel-collector-agent -n default
```
(Equivalently, re-run `scripts/01-install-otel-collector.sh` with `HEC_TOKEN=<new-token>` — the
manual patch above just avoids re-triggering the webhook cert-regen race described above.)

## Global Data Link's built-in "navigator" target doesn't select the entity
**Symptom:** a Global Data Link (Settings → Data Links) targeting the built-in **Splunk
Observability Cloud navigator** with property `host.name` lands on the unfiltered "Active hosts"
list — no host is selected, so the Related Content panel isn't shown.

**Root cause:** the built-in navigator target type doesn't pass a selection filter for the
matched property value.

**Fix:** use a **Custom URL** target instead, with a `mapSelection=` query param carrying the
value token. See `docs/DEMO_SCRIPT.md` → "One-time setup — Global Data Link" for the exact URL
shape and field values.

## Recommended clean-deploy order
```bash
k3d cluster create hybrid-cloud-rca-demo
# wait for: kubectl get nodes -> Ready
ACCESS_TOKEN=... REALM=... INSTANCE=... HEC_URL=... HEC_TOKEN=... \
  bash scripts/01-install-otel-collector.sh
K3D_CLUSTER=hybrid-cloud-rca-demo LLM_PROVIDER=... bash scripts/02-deploy-travel-planner.sh
bash scripts/03-inject-dns-failure.sh   # or 05/06 — each one resets to a clean baseline first
```
