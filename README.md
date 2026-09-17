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
**APM trace shows where a transaction failed → Related Content surfaces existing network/infra
monitoring log data for that host/time, right next to the trace → root cause confirmed without
leaving the workflow.**

## What's in this repo
- `travel-planner/` — a small OTel-instrumented Flask microservices app (orchestrator ->
  flight/hotel/activity agents -> synthesizer) that stands in for "the customer's transaction."
- `manifests/travel-planner/` — k3d/Kubernetes manifests to deploy it.
- `scripts/` — install the Splunk OTel Collector, deploy the app, and a worked-example
  DNS/on-prem-to-cloud failure scenario (`03-inject-dns-failure.sh` / `04-restore-services.sh`).
- `synthetic-network-data/` — generator that pushes SolarWinds/ExtraHop-shaped events via HEC, to
  stand in for a customer's existing network-monitoring telemetry without needing real hardware.
- `docs/PLAN.md` — phased build plan for standing this demo up.
- `docs/DEMO_SCRIPT.md` — step-by-step walkthrough of the DNS/on-prem-to-cloud scenario.

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
App, OTel Collector deploy scripts, the DNS/on-prem failure scenario, and the synthetic event
generator are built and working. Still open: provisioning the dedicated Splunk Platform +
Observability Cloud org pairing with Log Observer Connect configured between them — see
`docs/PLAN.md`.
