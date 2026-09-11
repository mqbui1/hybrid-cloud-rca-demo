# Demo Script — DNS/On-Prem-to-Cloud Failure Walkthrough

## Prerequisites
- travel-planner deployed (`scripts/01-install-otel-collector.sh`, `scripts/02-deploy-travel-planner.sh`)
- A dedicated Splunk Platform stack + Observability Cloud org, with Log Observer Connect
  configured between them (see `docs/PLAN.md` — infra provisioning is tracked separately, not
  yet complete as of this writing)
- `HEC_URL` / `HEC_TOKEN` for the Splunk Platform stack, to run the synthetic event generator

## The story
A transaction has to traverse on-prem infrastructure before reaching a cloud service. Today,
when something fails on that hop, the network team and the app team each have their own tools
and neither has the full picture. This walkthrough proves a single operational view can show
exactly where the failure is — using telemetry that's already flowing into Splunk, with no new
agent installed anywhere.

## Step 1 — Establish the healthy baseline
Send a normal request and confirm it succeeds end to end:
```bash
kubectl run -it --rm baseline-test --image=curlimages/curl --restart=Never -n travel-planner -- \
  curl -s -X POST http://orchestrator.travel-planner.svc.cluster.local:8080/plan \
    -H 'Content-Type: application/json' \
    -d '{"origin": "Seattle", "destination": "Paris", "travellers": 2}'
```
In APM: `orchestrator` → `travel.plan` → trace completes, all `agent.call.*` spans green.

Optionally seed a few minutes of healthy network telemetry so the "before" state looks realistic:
```bash
python3 synthetic-network-data/generate_events.py --scenario baseline \
  --host <k8s-node-hostname> --count 5
```

## Step 2 — Break it
```bash
bash scripts/03-inject-dns-failure.sh
```
This breaks DNS resolution on the orchestrator's hop to `flight-agent` — the flight-agent pod
itself stays healthy and reachable by IP; the orchestrator simply can no longer resolve the
hostname it needs, simulating a broken on-prem DNS relay.

## Step 3 — Check APM
`orchestrator` → `travel.plan` → open the new error trace.

**What you should see:** the trace completes (orchestrator caught the error and returned a
degraded response), but `agent.call.flight-agent` is an ERROR span with a DNS resolution failure
in the exception message (`Failed to resolve 'flight-agent.onprem-dns-relay.invalid'...`) — a
distinctly different signature from a plain connection-refused/service-down error.

**The gap this exposes:** APM can tell you the call failed and that it's DNS-shaped, but it
doesn't have visibility into *why* the resolver failed — that detail lives in the network
monitoring tooling.

## Step 4 — Generate the correlating network telemetry
```bash
python3 synthetic-network-data/generate_events.py --scenario dns-failure \
  --host <k8s-node-hostname>
```
This pushes a SolarWinds-style alert and an ExtraHop-style detection into the Splunk platform,
tagged with the same host and a timestamp overlapping the failing trace — standing in for
telemetry a customer's real SolarWinds/ExtraHop deployment would already be producing.

## Step 5 — Pivot via Log Observer Connect
From the failing span in APM, use Log Observer Connect to pivot into Splunk Platform log search
scoped to that host and time window. The SolarWinds alert and ExtraHop detection from Step 4
should appear, naming the on-prem relay node and describing the DNS resolution failure directly.

**The verdict:** APM told you where in the transaction it failed and that it was DNS-shaped;
one pivot — no new agent, no new tool — confirmed the root cause using telemetry that was
already there.

## Step 6 — Restore
```bash
bash scripts/04-restore-services.sh
```

## Discussion prompt
Today, would this failure surface as a network ticket, an app ticket, or both — and how long
would it take each team to converge on "it's the on-prem DNS relay"? Walk through what that
investigation actually looks like in your environment right now.
