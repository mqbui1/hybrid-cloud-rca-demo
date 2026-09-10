# Fannie Mae Hybrid Visibility Demo — Build Plan

## The question we're answering
Nimesh's actual ask: *"When a transaction moves across on-prem, network, AWS, and multiple
cloud services, can I determine exactly where it failed from a single operational view?"*
Not a generic Cloud Control product tour.

## Why not ThousandEyes
Fannie Mae doesn't use TE today, and Nimesh explicitly flagged new-agent-install friction as a
blocker. Their real network-visibility tools are **ExtraHop** and **SolarWinds**, already
integrated into Splunk via Splunkbase add-ons (SolarWinds Add-on 3584, ExtraHop Add-On 3938,
ExtraHop RevealX App 7708). These land data in **Splunk Cloud Platform** (logs/HEC), not natively
in O11y Cloud.

## The correlation mechanism: Log Observer Connect
Splunk O11y Cloud's **Log Observer Connect** lets you pivot from an APM trace/span directly into
Splunk Cloud Platform log search, scoped by host + time window — no new agent required. Fannie
Mae's real org already has the prerequisites on (US0 Unified Identity, US1 Log Observer Connect
confirmed enabled), so this mechanism is realistic for them, not hypothetical.

This is the core mechanic the demo needs to prove: **APM trace shows where a transaction failed
→ one click pivots into the ExtraHop/SolarWinds log data already sitting in Splunk Platform for
that host/time → root cause confirmed without leaving the workflow.**

## Why build externally instead of in Fannie Mae's org
No API/token access to their real org (their policy), and we shouldn't rehearse against a
customer's live environment anyway. Building a standalone lab that replicates the same mechanism
with synthetic data.

## What's done
- New repo `fannie-mae-hybrid-visibility-demo`, scaffolded from `te-o11y-integration`.
- Travel-planner Flask microservices app (orchestrator, flight/hotel/activity agents,
  synthesizer) ported with OTel instrumentation, ThousandEyes code fully stripped (no B3 headers,
  no TE test/agent env vars).
- k3d manifests + OTel Collector install script ported and renamed to this demo's own
  namespace/secrets/index (`fannie-mae-hybrid-visibility-demo`), decoupled from the shared
  workshop stack.
- Investigated infra provisioning: confirmed a self-serve CO2 (`cloudctl`/`sadmin`) path exists
  for the **Splunk Cloud Platform** side of a dedicated stack — see
  `docs/INFRA_PROVISIONING.md`. Not yet executed (live/costly action, needs go-ahead).

## Phased plan

**Phase 1 — Infra (blocking everything else)**
1. Provision a dedicated Splunk Cloud Platform stack via CO2 (`ca_adhoc` template gives open
   HEC/API for dev/test) — real infra + purchase order, needs explicit go-ahead before running.
2. Provision a dedicated Splunk O11y Cloud org. **Open question — no confirmed internal
   self-serve path found yet.** *Ask Somen*: he mentioned building a similar stack+org pairing
   before — how did he provision the O11y org side?
3. Configure Log Observer Connect between the two (admin access on both, unlike the shared
   workshop stack where participants can't do this).

**Phase 2 — Synthetic telemetry**
4. Build a synthetic ExtraHop/SolarWinds event generator that pushes to Splunk Platform via HEC,
   mirroring the real add-ons' event schemas (3584/3938/7708), tagged with host/time so it lines
   up with APM trace spans for the pivot to work.

**Phase 3 — Failure scenario**
5. Build a new failure-injection scenario matching Nimesh's exact example: DNS/reverse-lookup
   issue between on-prem and AWS on a transaction hop (distinct from the app's existing 3 generic
   failure scenarios).

**Phase 4 — Demo script**
6. Write the walkthrough: problem framing → transaction journey in APM → inject the DNS/on-prem
   failure → show the failed span → pivot via Log Observer Connect into the synthetic
   ExtraHop/SolarWinds log showing the actual network-layer cause → single-pane RCA moment.

## Open decisions to review with Somen/Crystal this afternoon
1. **O11y org provisioning** — does Somen have a repeatable way to spin up a dedicated org (from
   the pairing he built previously), or do we need a trial signup?
2. **Go-ahead to run the CO2 stack creation** — real infra + commerce-plan purchase order, once
   the O11y side is resolved so both can be provisioned together.
3. **Scope check** — does this phased plan match what Somen/Crystal committed to as the "Cloud
   Control / Hybrid Visibility Follow-up" next step, or does anything need to be re-scoped before
   building further?

## Explicitly not deployed/executed yet
No CO2 stack, no O11y org, no k3d cluster has been created for this demo. Everything above is
code/docs only, pending the decisions in this call.
