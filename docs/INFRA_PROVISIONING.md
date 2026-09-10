# Provisioning a dedicated Splunk Cloud Platform + O11y Cloud pairing

Per decision: this demo needs a **dedicated** stack/org pairing with full admin access
(distinct from the shared `o11y-workshop-amer.splunkcloud.com` workshop stack used by
te-o11y-integration, where participants lack admin and can't configure Log Observer Connect).

## Splunk Cloud Platform side — CONFIRMED viable path (CO2 self-serve)

Internal Splunk engineers can self-provision a real staging Splunk Cloud Platform stack via
`cloudctl` + `sadmin`. Both CLIs are already installed locally (`/opt/homebrew/bin/cloudctl`,
`/opt/homebrew/bin/sadmin`), and the provisioning repo is already checked out at
`~/Documents/splunk-ai-canvas/packages/co2-stack-creation`.

- Template: `templates/ca_adhoc.yaml` (Cloud Control/AI Canvas features are enabled by this
  template but irrelevant/unused here — no other non-Cloud-Control template exists in this repo).
- Confirmed from the template: `hecWhitelist: ["0.0.0.0/0"]` and `apiAllowlistIP: ["0.0.0.0/0"]`
  — i.e. open HEC ingestion and API access for dev/test, which is exactly what's needed to push
  synthetic ExtraHop/SolarWinds events (task #5) and configure Log Observer Connect (task #3).
- Requires: Splunk US West Full Tunnel VPN (or Cisco VPN), `cloudctl`/`sadmin` auth permission.
- Recommended invocation: the `create-co2-stack` skill (in `~/Documents/splunk-ai-canvas`,
  `.claude/skills/create-co2-stack`) — collects inputs, renders exact commands, requires explicit
  approval before creating the stack and a second fresh approval before the purchase-order step
  (auth codes expire after 5 min).
- This is a **live external side effect** (real infra + a commerce-plan purchase order) — do not
  run without the engineer's explicit go-ahead each time, per the skill's own approval boundary.

Manual command shape (for reference, not yet executed):
```bash
cd ~/Documents/splunk-ai-canvas/packages/co2-stack-creation
./create_co2_stack.sh --name '<stack-name>' --environment 'stg' \
  --version '<splunk-version>' --template_file 'templates/ca_adhoc.yaml'
./create_purchase_order.sh --name '<stack-name>' --environment 'stg' \
  --first_name '<first>' --last_name '<last>' --email '<email>'
```

## O11y Cloud org side — UNRESOLVED

No internal self-serve org-creation tooling for a fresh Splunk Observability Cloud org was found
in prior memory/notes. The CO2 process above only provisions the Splunk Cloud Platform (Splunk
Enterprise Cloud) side — `cloud_control_integration_enabled` wires Cloud Control into an
**existing** O11y org via unified identity, it does not create a new O11y org.

Need to confirm with the account/SE team whether there's an internal "spin up a dedicated O11y
Cloud trial/demo org" process, or whether a standard self-serve signup (e.g. a free/trial O11y
org) is acceptable for this lab.

## Status
Blocked on: (1) explicit go-ahead to run the CO2 stack-creation commands above, (2) an O11y org
provisioning path.
