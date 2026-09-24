# Hybrid Cloud RCA Demo

A reusable demo pattern showing how to answer a common enterprise question:

> "When a transaction moves across on-prem, network, AWS, and multiple cloud services, can I
> determine exactly where it failed from a single operational view?"

This is not a generic APM product tour — it demonstrates a specific correlation mechanism that
works with tooling most enterprises already have, without requiring a new synthetic-monitoring
agent to be installed anywhere.

## The pattern

Many enterprises already run network/infrastructure monitoring tools (e.g. ExtraHop, SolarWinds,
ThousandEyes, etc.) that push data into a Splunk platform, but that data isn't natively part of
an APM trace. The bridge is Splunk Observability Cloud's **Related Content** feature, which
surfaces logs next to a trace/span — with **Log Observer Connect** as the prerequisite
integration that makes Splunk Platform logs available to it in the first place. No new agent
required, as long as:
- The org has Unified Identity + Log Observer Connect configured between the Observability Cloud
  org and the Splunk Platform stack
- Entity-index mapping is enabled for Related Content (logs) on the relevant index
- The log events and the span/host share a matching correlation field — in practice `host.name`,
  since standalone network-monitoring events aren't tied to a trace/span ID

The demo mechanic:
**APM trace shows where a transaction failed → note the host off the failing span → the
Infrastructure host entity page's Related Content surfaces existing network/infra monitoring log
data for that host/time → root cause confirmed without leaving the workflow.** (The trace view's
own automatic Related Content → Infrastructure tile does not reliably link to this data in
practice — see `docs/DEMO_SCRIPT.md` for why — so the pivot goes through the host entity page.)

## What's in this repo
- `travel-planner/` — a small OTel-instrumented Flask microservices app (orchestrator ->
  flight/hotel/activity/currency agents -> synthesizer) that stands in for "the customer's
  transaction." `currency-agent` is tagged `cloud.provider=azure` while everything else is
  tagged `aws`, to stand in for a hop that crosses cloud providers.
- `manifests/travel-planner/` — k3d/Kubernetes manifests to deploy it.
- `scripts/` — install the Splunk OTel Collector, deploy the app, and three worked-example
  failure scenarios: DNS/on-prem-to-cloud (`03-inject-dns-failure.sh`), cloud-side load-balancer
  target-unhealthy (`05-inject-lb-failure.sh`), and cross-cloud connectivity
  (`06-inject-multicloud-failure.sh`); restore any of them with `04-restore-services.sh`.
- `synthetic-network-data/` — generator that pushes SolarWinds/ExtraHop-shaped events via HEC, to
  stand in for a customer's existing network-monitoring telemetry without needing real hardware.
- `docs/PLAN.md` — phased build plan for standing this demo up.
- `docs/DEMO_SCRIPT.md` — step-by-step walkthrough of the DNS/on-prem-to-cloud scenario.
- `docs/DEMO_SCRIPT_LB_FAILURE.md` — step-by-step walkthrough of the load-balancer scenario.
- `docs/DEMO_SCRIPT_MULTICLOUD_FAILURE.md` — step-by-step walkthrough of the cross-cloud
  connectivity scenario.
- `docs/TROUBLESHOOTING.md` — deployment lessons learned (Docker resource contention, Helm/webhook
  race conditions on first install, etc.) so a fresh deploy goes smoothly.

## Demo scenarios in detail

All three scenarios share the same investigation pattern (break something → look at the APM
trace → note the failing span's host → pivot through the Infrastructure host entity page's
Related Content → find the pre-existing network/infra alert that explains the failure) but each
demonstrates a different failure signature and a different part of the transaction path.

### 1. DNS / on-prem-to-cloud failure
- **Files:** `scripts/03-inject-dns-failure.sh`, `docs/DEMO_SCRIPT.md`
- **What it simulates:** the orchestrator's `FLIGHT_AGENT_URL` is patched to an unresolvable
  hostname — a broken on-prem DNS relay that can't resolve a cloud-hosted service's name.
- **Signature in APM:** `agent.call.flight-agent` errors with a name-resolution failure (no
  connection ever attempted), distinct from an HTTP error.
- **Correlating telemetry:** SolarWinds "DNS Server Unreachable" alert + ExtraHop "DNS
  Resolution Failures Detected" detection, tagged to the on-prem relay device.
- **Status:** verified end-to-end live (Related Content pivot + Severity display confirmed).

### 2. Load-balancer target-unhealthy failure
- **Files:** `scripts/05-inject-lb-failure.sh`, `docs/DEMO_SCRIPT_LB_FAILURE.md`
- **What it simulates:** `flight-agent` is marked unhealthy by its cloud load balancer (failing
  health checks, removed from rotation) — the pod itself stays up and DNS resolves fine, but
  every request now returns a clean HTTP 503.
- **Signature in APM:** `agent.call.flight-agent` errors with a clean HTTP 503 — a reachable
  service actively refusing traffic, not a resolution failure.
- **Correlating telemetry:** SolarWinds "Target Group Unhealthy" alert + ExtraHop "Elevated 5xx
  Error Rate at Load Balancer" detection, tagged to the ALB device.
- **Status:** verified end-to-end live (Related Content pivot + Severity display confirmed,
  5/5 events correctly scoped, no unscoped noise).

### 3. Cross-cloud (AWS -> Azure) connectivity failure
- **Files:** `scripts/06-inject-multicloud-failure.sh`, `docs/DEMO_SCRIPT_MULTICLOUD_FAILURE.md`
- **What it simulates:** `currency-agent` is deployed and tagged `cloud.provider=azure` /
  `cloud.region=eastus2` while every other service is tagged `aws` / `us-west-2` — a specialist
  hop that lives in a second cloud provider. The scenario drops the network path between them
  (a VPC/VNet peering route going dark), which is a **silent** failure: no DNS error, no clean
  HTTP error, just a hang.
- **Signature in APM:** `agent.call.currency-agent` (the orchestrator's client span) times out
  after the orchestrator's 5s per-call timeout — `ERROR: ReadTimeout`, no HTTP status at all,
  since the request never got a response. `currency-agent`'s own server span (`POST /invoke`)
  shows no error — it's healthy the whole time, just sleeping for 30s before returning a normal
  200, so the *destination* looks completely fine even though the *caller* already gave up. That
  asymmetry — one side errors, the other side reports nothing wrong — is the point: it's what a
  silently dropped route looks like from APM alone, and it's why the overall trace duration runs
  ~30s (bounded by currency-agent's span) even though the user-facing failure resolves at ~5s.
  `cloud.provider`/`cloud.region` on the currency-agent spans read `azure`/`eastus2` vs.
  `aws`/`us-west-2` on every other agent span in the same trace.
- **Correlating telemetry:** SolarWinds "Route Propagation Failure" alert + ExtraHop "Cross-Cloud
  Peering Connection Down" detection, tagged to a simulated VNet/VPC peering connection.
- **Status:** verified end-to-end live (Related Content pivot + Severity display confirmed).

## Customizing for a specific customer/engagement
This repo is intentionally generic. To adapt it for a real account:
1. Swap the failure scenario to match their actual transaction path (e.g. DNS/reverse-lookup
   between on-prem and cloud, a specific network hop, a specific cloud service).
2. Build a synthetic event generator matching the schema of whatever network/infra monitoring
   tool they actually use (check their Splunk platform add-ons for the exact event schema).
3. Tag synthetic events with the exact `host.name` value the OTel Collector already stamps on
   the span (see `docs/DEMO_SCRIPT.md`) so Related Content can resolve the correlation.
4. Keep customer names, transcripts, and account-specific planning notes **out of this repo** —
   track those separately (internal notes, not committed here).

## Status
App, OTel Collector deploy scripts, all three failure scenarios, and the synthetic event
generator are built. All three scenarios (DNS, load-balancer, cross-cloud) are verified
end-to-end — including Related Content pivot and Severity-column display — against a live
Splunk Platform + Observability Cloud org pair.
