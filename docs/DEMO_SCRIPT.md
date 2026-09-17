# Demo Script — DNS/On-Prem-to-Cloud Failure Walkthrough

## Prerequisites
- travel-planner deployed (`scripts/01-install-otel-collector.sh`, `scripts/02-deploy-travel-planner.sh`)
- A dedicated Splunk Platform stack + Observability Cloud org, with Log Observer Connect
  configured between them (see `docs/PLAN.md` — infra provisioning is tracked separately, not
  yet complete as of this writing)
- Entity-index mapping enabled for **Related Content (logs)** on the index you're using
  (Log Observer → Settings → Entity-Index Mapping for Related Content (logs) → select the LOC
  connection → generate/add mappings for `hybrid-cloud-rca-demo`). Without this, Related Content
  will not surface the synthetic log events in Step 5 even if the host values match exactly.
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

Get the host value that Related Content will need to match on later — the k8s node the
`flight-agent` pod actually runs on (this is the same `host.name` the Splunk OTel Collector's
resource detection sets on the span automatically):
```bash
export CORRELATING_HOST=$(kubectl get pod -n travel-planner -l app=flight-agent \
  -o jsonpath='{.items[0].spec.nodeName}')
```

Optionally seed a few minutes of healthy network telemetry so the "before" state looks realistic:
```bash
python3 synthetic-network-data/generate_events.py --scenario baseline \
  --host "${CORRELATING_HOST}" --count 5
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
  --host "${CORRELATING_HOST}"
```
This pushes a SolarWinds-style alert and an ExtraHop-style detection into the Splunk platform.
The `--host` value must be **exactly** the k8s node hostname captured in Step 1 — that's the same
`host.name` value the OTel Collector already stamped on the failing span, and it's the only field
these two records can be correlated on (see below).

## Step 5 — Pivot via Related Content
This pivot is Splunk's **Related Content** feature, not a direct "click a link" action — Log
Observer Connect is the prerequisite integration that makes Splunk Platform logs available to it;
Related Content is what actually surfaces them next to the trace.

Related Content can correlate two ways: by matching `trace_id`/`span_id` on the log line, or by
matching `host.name`. Our synthetic SolarWinds/ExtraHop events aren't tied to any trace, so the
`host.name` path is the one that applies here — which is why the `--host` value in Step 4 has to
be exact.

In APM, open the failing trace/span from Step 3 and check the Related Content bar at the bottom
of the screen — it should show a tile for related log lines on that host. Select it to open Log
Observer, filtered to that host and time window. The SolarWinds alert and ExtraHop detection from
Step 4 should appear there, naming the on-prem relay node and describing the DNS resolution
failure directly.

If the tile doesn't appear, check (in order): the `--host` value matches the pod's node name
exactly, the HEC events landed in the index that has entity-index mapping enabled (see
Prerequisites), and Related Content for logs hasn't been deactivated in APM Settings → General
Settings.

**The verdict:** APM told you where in the transaction it failed and that it was DNS-shaped;
Related Content — no new agent, no new tool — surfaced the network-layer log data that confirmed
the actual root cause.

## Step 6 — Restore
```bash
bash scripts/04-restore-services.sh
```

## Discussion prompt
Today, would this failure surface as a network ticket, an app ticket, or both — and how long
would it take each team to converge on "it's the on-prem DNS relay"? Walk through what that
investigation actually looks like in your environment right now.
