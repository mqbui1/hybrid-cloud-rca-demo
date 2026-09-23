# Demo Script — DNS/On-Prem-to-Cloud Failure Walkthrough

## Prerequisites
- travel-planner deployed (`scripts/01-install-otel-collector.sh`, `scripts/02-deploy-travel-planner.sh`)
- A dedicated Splunk Platform stack + Observability Cloud org, with Log Observer Connect
  configured between them (see `docs/PLAN.md` — infra provisioning is tracked separately, not
  yet complete as of this writing)
- On the LOC connection (Data Management → Log Observer Connect → your connection), **disable
  "Similar/Global Index Search"**. With it on, log search results blend in unscoped matches from
  every index and the connection banners warn results "may not be scoped for host/time" — this
  makes Related Content look like it's working when it isn't actually correlating on anything.
- Entity-index mapping enabled for **Related Content (logs)** on the index you're using
  (Log Observer → Settings → Entity-Index Mapping for Related Content (logs) → select the LOC
  connection → add mappings for `host.name` and `k8s.node.name` → `hybrid-cloud-rca-demo`).
- `HEC_URL` / `HEC_TOKEN` for the Splunk Platform stack, to run the synthetic event generator

> **How this pivot correlates:** APM's trace-view "Related Logs" widget (the one that auto-loads
> at the bottom of a trace) only keyword-matches on `trace_id` — it can't be used here, since real
> SolarWinds/ExtraHop tools have no visibility into application trace context and it would be
> unrealistic to expect a customer to inject one. The trace's "Related Content → Infrastructure"
> tile is also not usable — confirmed (on a fresh trace, not a sync-delay artifact) to return
> "No related results" in this org, even though the reverse direction works (an Infrastructure
> Container entity's Related Content *can* pivot into APM). This walkthrough instead pivots
> manually: read `host.name`/the pod name directly off the span's own **Process** tags panel in
> APM, then navigate to **Infrastructure → Host entity page's Related Content**, which correlates
> by `host.name` + time window — the same dimension real network-monitoring tools already tag
> their alerts with.

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

Get the host value Related Content will correlate on later — the k8s node the `flight-agent` pod
runs on (this is the same `host.name` the Splunk OTel Collector's resource detection sets on the
span automatically):
```bash
export CORRELATING_HOST=$(kubectl get pod -n travel-planner -l app=flight-agent \
  -o jsonpath='{.items[0].spec.nodeName}')
```
(`CORRELATING_HOST` is only needed for the `generate_events.py` script call in Step 4 — when
presenting live, skip the terminal and just point at `host.name` in the failing span's own
**Process** tags panel in Step 3, which shows the identical value.)

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
This pushes a SolarWinds-style alert and an ExtraHop-style detection into the Splunk platform,
tagged with the same `host` value as the failing span's `host.name`/`k8s.node.name` — the only
field these two systems can realistically be correlated on.

## Step 5 — Pivot via Related Content
Go to **Infrastructure → Hosts → `${CORRELATING_HOST}`** and open **Related Content → Logs**.
It should show a tile for related log lines on that host, scoped to a time window around now.
Select it to open Log Observer, filtered to that host/time. The SolarWinds alert and ExtraHop
detection from Step 4 should appear, naming the on-prem relay node and describing the DNS
resolution failure directly.

If the tile doesn't appear, or results look unscoped, check (in order): `CORRELATING_HOST` matches
the pod's node name exactly, the HEC events landed in the index that has entity-index mapping
enabled (see Prerequisites), and "Similar/Global Index Search" is disabled on the LOC connection
(see Prerequisites).

In the Logs table, click the **Severity** column header to sort descending — the synthetic
Critical alert surfaces at the top instead of being buried among routine app log lines.

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
