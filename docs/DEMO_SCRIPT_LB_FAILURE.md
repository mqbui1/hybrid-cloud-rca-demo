# Demo Script — Load-Balancer Target-Unhealthy Failure Walkthrough

Shares prerequisites and correlation mechanism with `docs/DEMO_SCRIPT.md` (Log Observer Connect,
entity-index mapping, "Similar/Global Index Search" disabled, host+time correlation via the
Infrastructure host entity page) — see that doc for the full prerequisites list, including why the
automatic APM trace → Related Content → Infrastructure tile isn't used (confirmed non-functional
in this org; the manual "read `host.name` off the span" pivot is used instead). This walkthrough
covers a different failure signature on the same transaction path.

## The story
Nimesh's own framing of the problem wasn't just DNS — a transaction "can fail on any device...
network load balancer, or any devices inside on-prem." This scenario shows the same RCA pattern
at a different point in the journey: the cloud-side load balancer marks the backend unhealthy and
starts failing requests, while the app itself never breaks.

## Step 1 — Establish the healthy baseline
Same as `docs/DEMO_SCRIPT.md` Step 1 — send a normal `/plan` request, confirm it succeeds, and
capture `CORRELATING_HOST`:
```bash
export CORRELATING_HOST=$(kubectl get pod -n travel-planner -l app=flight-agent \
  -o jsonpath='{.items[0].spec.nodeName}')
```

## Step 2 — Break it
```bash
bash scripts/05-inject-lb-failure.sh
```
This marks `flight-agent` unhealthy (simulating a failed LB health check / target removed from
rotation) — the pod stays up and DNS resolves fine, but every request now returns HTTP 503.

## Step 3 — Check APM
`orchestrator` → `travel.plan` → open the new error trace.

**What you should see:** `agent.call.flight-agent` is an ERROR span with an HTTP 503 status —
a distinctly different signature from the DNS scenario's name-resolution failure. The service
is reachable; it's just refusing/failing to serve traffic.

**The gap this exposes:** APM can tell you the call failed with a 503, but it doesn't know
*why* the load balancer stopped routing to this target — that detail lives in the network
monitoring tooling.

## Step 4 — Generate the correlating network telemetry
```bash
python3 synthetic-network-data/generate_events.py --scenario lb-failure \
  --host "${CORRELATING_HOST}"
```
This pushes a SolarWinds-style alert ("Target Group Unhealthy") and an ExtraHop-style detection
("Elevated 5xx Error Rate at Load Balancer") into the Splunk platform, tagged with the same host
value as the failing span.

## Step 5 — Pivot via Related Content
Same mechanism as the DNS scenario: **Infrastructure → Hosts → `${CORRELATING_HOST}`** → Related
Content → Logs. The SolarWinds alert and ExtraHop detection from Step 4 should appear, naming the
load balancer and describing the health-check failure directly. Click the **Severity** column
header to sort descending so the Critical alert surfaces at the top.

**The verdict:** APM told you the call failed with a 503; Related Content surfaced the
load-balancer-level alert that explains why — a different root cause, same operational view.

## Step 6 — Restore
```bash
bash scripts/04-restore-services.sh
```

## Discussion prompt
This is a different failure mode than DNS (network device health vs. resolution), but the
investigation path is identical from the operator's seat. Would your team currently know it was
an LB health-check issue and not an app bug, and how would you find out today?
