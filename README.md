# Fannie Mae Hybrid Visibility Demo

External lab environment for the Cisco Cloud Control / hybrid-cloud RCA follow-up demo for
Nimesh (Fannie Mae). Built standalone — not against Fannie Mae's real O11y Cloud org (they don't
grant API/token access to Splunk engineers, and this needs to be rehearsed/iterated on freely).

## The use case being demonstrated
Nimesh's own example: a transaction to FannieMae.com doesn't go directly to AWS — it traverses
DNS, does a reverse lookup, routes through on-prem infrastructure, then out to AWS and back. When
something fails along that path (app, network, load balancer, on-prem device, cloud service), he
wants a single operational view that shows exactly where.

Key ask, in his words: *"When an application transaction moves across on premises, network, AWS,
and multiple cloud services, can I determine exactly where it failed from a single operational
view?"* He explicitly does not want a generic Cloud Control product demo, feature tour, or
dashboard clicking — and does not want assumptions or over-expectations about what the platform
can/can't do.

## Why this isn't built on ThousandEyes
Fannie Mae doesn't use ThousandEyes, and Nimesh flagged deploying a new agent as a blocker. They
already run **ExtraHop and SolarWinds**, both pushing data into Splunk Cloud Platform (core) today
via the SolarWinds Add-on (splunkbase.com/app/3584) and ExtraHop Add-On (splunkbase.com/app/3938).

## Correlation mechanism: Log Observer Connect
Fannie Mae already has the prerequisites for this in their real org (US0: Unified Identity, US1:
Log Observer Connect enabled) — meaning an APM trace/span can pivot directly into Splunk Platform
log search by host/time, surfacing their existing ExtraHop/SolarWinds data. This demo replicates
that mechanism in a standalone lab:
- A demo Splunk Cloud Platform stack + a demo O11y Cloud org, with Log Observer Connect enabled
  between them
- Synthetic events pushed via HEC that mirror the SolarWinds/ExtraHop add-on schemas (no real
  ExtraHop/SolarWinds hardware needed)
- The travel-planner OTel app (ported from te-o11y-integration) tagged with matching host
  identifiers so the time/host correlation actually resolves

## What's reused from te-o11y-integration
- OTel Collector install script
- travel-planner app (orchestrator -> flight/hotel/activity agents -> synthesizer)
- k3d/EC2 deploy pattern

## What's new here
- No ThousandEyes Enterprise Agent, no TE test creation — dropped entirely
- Synthetic ExtraHop/SolarWinds event generator (`synthetic-network-data/`)
- A new failure scenario matching Nimesh's exact DNS/on-prem/AWS example (none of
  te-o11y-integration's existing scenarios cover this)
- Log Observer Connect setup docs (`docs/LOG_OBSERVER_CONNECT_SETUP.md`)

## Status
Scaffolding in progress. See `docs/` for setup requirements as they're written.
