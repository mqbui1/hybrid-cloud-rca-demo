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
3. Configure Log Observer Connect between the two.

**Phase 2 — Synthetic telemetry**
4. Build a synthetic network/infra-monitoring event generator that pushes to the Splunk platform
   via HEC, matching the schema of whichever real tool is being represented, tagged with
   host/time so it lines up with APM trace spans for the pivot to work.

**Phase 3 — Failure scenario**
5. Build a failure-injection scenario matching the specific transaction path being demonstrated
   (e.g. DNS/reverse-lookup issue between on-prem and cloud on a transaction hop).

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
