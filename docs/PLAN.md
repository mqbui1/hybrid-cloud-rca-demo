# Build Plan

## The question this demo answers
"When a transaction moves across on-prem, network, AWS, and multiple cloud services, can I
determine exactly where it failed from a single operational view?" — not a generic APM product
tour.

## Why not a synthetic-monitoring agent (e.g. ThousandEyes)
Many customers already have network-visibility tooling in place (ExtraHop, SolarWinds, etc.) and
are reluctant to deploy a new agent just for a demo. This pattern uses whatever network/infra
monitoring data the customer already pushes into a Splunk platform, instead of requiring a new
tool.

## The correlation mechanism: Log Observer Connect
Splunk Observability Cloud's **Log Observer Connect** lets you pivot from an APM trace/span
directly into Splunk Platform log search, scoped by host + time window — no new agent required,
given Unified Identity + Log Observer Connect are enabled between the org and the platform stack.

Core mechanic: **APM trace shows where a transaction failed → one click pivots into the
network/infra log data already sitting in the Splunk platform for that host/time → root cause
confirmed without leaving the workflow.**

## Why build in a standalone lab instead of a customer's real org
Most enterprise accounts won't grant API/token access to their production Splunk org, and a demo
shouldn't be rehearsed against a live customer environment anyway. This repo builds a standalone
lab that replicates the same mechanism with synthetic data, decoupled from any specific customer.

## What's done
- Travel-planner Flask microservices app (orchestrator, flight/hotel/activity agents,
  synthesizer) with OTel instrumentation.
- k3d manifests + OTel Collector install script, parameterized by `INSTANCE`/`HEC_URL`/`HEC_TOKEN`
  env vars so they aren't tied to any one org.

## Phased plan

**Phase 1 — Infra (blocking everything else)**
1. Provision a dedicated Splunk Platform stack with admin access and open HEC ingestion for
   dev/test.
2. Provision a dedicated Splunk Observability Cloud org with admin access.
3. Configure Log Observer Connect between the two, then enable entity-index mapping for
   Related Content (logs) on the index being used — Related Content won't surface correlated
   logs without this, even with Log Observer Connect on and matching host values.

**Phase 2 — Synthetic telemetry**
4. Build a synthetic network/infra-monitoring event generator that pushes to the Splunk platform
   via HEC, matching the schema of whichever real tool is being represented, tagged with
   host/time so it lines up with APM trace spans for the pivot to work.

**Phase 3 — Failure scenario**
5. Build a failure-injection scenario matching the specific transaction path being demonstrated
   (e.g. DNS/reverse-lookup issue between on-prem and cloud on a transaction hop). **Done** —
   `scripts/03-inject-dns-failure.sh` / `docs/DEMO_SCRIPT.md`.
6. **Done** — load-balancer/device failure on the cloud-side hop. Nimesh's own worked example
   (on-prem → DNS → AWS ALB → back) wasn't just DNS — he explicitly called out that a transaction
   "can fail on any device... network load balancer, or any devices inside on-prem."
   `scripts/05-inject-lb-failure.sh` / `docs/DEMO_SCRIPT_LB_FAILURE.md` simulate flight-agent being
   marked unhealthy by its LB (HTTP 503s), correlated via host+time through the Infrastructure
   host entity page — verified end to end (SolarWinds "Target Group Unhealthy" alert surfaced
   correctly scoped, 5/5 events, no unscoped noise).
7. **True multi-cloud hop failure.** Nimesh's stated #1 concern on the Cisco Cloud Control
   call: "we have multi-cloud... different data formats and different ways data has been
   collected. How do you bring all these things together?" Added a second cloud leg:
   `currency-agent` is deployed and tagged `cloud.provider=azure`/`cloud.region=eastus2` while
   the orchestrator and every other agent are tagged `aws`/`us-west-2`. `CROSS_CLOUD_UNREACHABLE`
   env var makes the agent hang instead of erroring, simulating a dropped VPC/VNet peering
   route. `scripts/06-inject-multicloud-failure.sh` / `docs/DEMO_SCRIPT_MULTICLOUD_FAILURE.md`
   walk through it, correlated the same host+time way via the Infrastructure host entity page.
   Built but not yet verified live end-to-end (see README Status).

**Phase 4 — Demo script**
6. Write the walkthrough: problem framing → transaction journey in APM → inject the failure →
   show the failed span → pivot via Log Observer Connect into the synthetic log data showing the
   actual root cause → single-pane RCA moment.

## Open decisions before building further
1. **Infra provisioning path** — how the dedicated Splunk Platform stack + Observability Cloud
   org pairing gets provisioned (internal process notes are tracked separately, not in this repo).
2. **Scope check** — confirm the phased plan matches what's actually needed before building
   further.

## Explicitly not deployed/executed yet
No stack, no org, no cluster has been created for this demo. Everything above is code/docs only.
