# Demo Script — Multi-Cloud (AWS -> Azure) Connectivity Failure Walkthrough

Shares prerequisites and correlation mechanism with `docs/DEMO_SCRIPT.md` (Log Observer Connect,
entity-index mapping, "Similar/Global Index Search" disabled, host+time correlation via the
Infrastructure host entity page) — see that doc for the full prerequisites list, including why the
automatic APM trace → Related Content → Infrastructure tile isn't used (confirmed non-functional
in this org; the manual "read `host.name` off the span" pivot is used instead). This walkthrough
covers a different transaction path: a hop that crosses cloud providers, not on-prem-to-cloud or a
single cloud's own load balancer.

## The story
Not every hybrid failure is on-prem-to-cloud. Once a transaction fans out across multiple
specialist services, some of those services may live in a *different* cloud provider than the
rest of the app (e.g. a third-party FX-rate service, an M&A-inherited workload, a
best-of-breed SaaS integration). `currency-agent` is deployed and tagged as if it runs in Azure
(`cloud.provider=azure`) while the orchestrator and every other agent are tagged AWS
(`cloud.provider=aws`) — see `manifests/travel-planner/currency-agent.yaml` and
`orchestrator.yaml`. This scenario simulates the cross-cloud network path between them going
dark (a dropped VPC/VNet peering route), which is a *silent* failure — no DNS error, no clean
HTTP error, just a hang until the caller's own timeout fires.

## Step 1 — Establish the healthy baseline
Same as `docs/DEMO_SCRIPT.md` Step 1 — send a normal `/plan` request, confirm it succeeds. This
scenario correlates on the **currency-agent** pod's node, not flight-agent's:
```bash
export CORRELATING_HOST=$(kubectl get pod -n travel-planner -l app=currency-agent \
  -o jsonpath='{.items[0].spec.nodeName}')
```

## Step 2 — Break it
```bash
bash scripts/06-inject-multicloud-failure.sh
```
This sets `CROSS_CLOUD_UNREACHABLE=true` on `currency-agent`, which makes every `/invoke` call
sleep for 30 seconds instead of responding — simulating a dropped cross-cloud route rather than
an active rejection. The orchestrator's own per-call timeout (5s) fires first, so the end-to-end
`/plan` request still completes in a few seconds with "Currency info unavailable," but the
underlying `agent.call.currency-agent` span shows the real story.

## Step 3 — Check APM
`orchestrator` → `travel.plan` → open the new error trace.

**What you should see:** `agent.call.currency-agent` is an ERROR span showing a client-side
timeout (no HTTP status code, unlike the LB scenario's clean 503) — the request never got a
response at all. Open the span's **Process** tags panel and compare `cloud.provider`/
`cloud.region` on this span vs. any `agent.call.flight-agent`/`hotel-agent`/`activity-agent`
span in the same trace: the failing hop is the only one tagged `azure`/`eastus2`, everything
else is `aws`/`us-west-2`.

**The gap this exposes:** APM can tell you this specific hop timed out and that it's tagged as
a different cloud provider, but it has no visibility into *why* the cross-cloud path is
down — that's peering/route-table/transit-gateway health, which lives in network monitoring
tooling, not APM.

## Step 4 — Generate the correlating network telemetry
```bash
python3 synthetic-network-data/generate_events.py --scenario multicloud-failure \
  --host "${CORRELATING_HOST}"
```
This pushes a SolarWinds-style alert ("Route Propagation Failure") and an ExtraHop-style
detection ("Cross-Cloud Peering Connection Down") into the Splunk platform, tagged with the same
host value as the failing span's node.

## Step 5 — Pivot via Related Content
Same mechanism as the other scenarios: **Infrastructure → Hosts → `${CORRELATING_HOST}`** →
Related Content → Logs. The SolarWinds alert and ExtraHop detection from Step 4 should appear,
naming the peering connection and describing the dropped-route condition directly. Click the
**Severity** column header to sort descending so the Critical alert surfaces at the top.

**The verdict:** APM told you a single cross-cloud hop hung and timed out; Related Content
surfaced the peering/route-table alert that explains why — without the operator needing to
guess which of two cloud providers' consoles to go check first.

## Step 6 — Restore
```bash
bash scripts/04-restore-services.sh
```

## Discussion prompt
This failure mode is silent (a hang, not an error) and spans two cloud providers' worth of
infrastructure. Would your team currently know within minutes that this was a cross-cloud
routing issue rather than an app bug, and which team/console would they check first?
