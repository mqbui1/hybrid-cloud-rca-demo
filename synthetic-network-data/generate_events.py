#!/usr/bin/env python3
"""
Synthetic network/infra-monitoring event generator.

Pushes events to a Splunk platform via HEC that mirror the general event
shape of common network-monitoring Splunk add-ons (SolarWinds Orion alerts,
ExtraHop RevealX detections), so a demo can show APM trace failures pivoting
(via Log Observer Connect) into "existing" network-layer telemetry — without
needing real SolarWinds/ExtraHop hardware or licenses.

These are illustrative shapes based on the public field names each add-on
documents, not a byte-exact reproduction of either vendor's schema.

Correlation is host + time window only (the `host` HEC field, matched against
the failing span's `host.name`/`k8s.node.name` via the Infrastructure host
entity page's Related Content) — not trace_id. Real SolarWinds/ExtraHop
deployments have no visibility into application trace context, so this
generator intentionally doesn't fabricate any.

Usage:
  export HEC_URL=https://<stack>.splunkcloud.com:8088
  export HEC_TOKEN=<hec-token>
  python3 generate_events.py --scenario dns-failure --host <k8s-node-hostname>
  python3 generate_events.py --scenario lb-failure --host <k8s-node-hostname>
  python3 generate_events.py --scenario multicloud-failure --host <k8s-node-hostname>
  python3 generate_events.py --scenario baseline --host <k8s-node-hostname> --count 5
"""
import argparse
import json
import os
import random
import time

import requests


def _post_event(hec_url: str, hec_token: str, index: str, host: str,
                 sourcetype: str, event: dict, event_time: float) -> None:
    resp = requests.post(
        f"{hec_url.rstrip('/')}/services/collector/event",
        headers={"Authorization": f"Splunk {hec_token}"},
        json={
            "time": event_time,
            "host": host,
            "index": index,
            "sourcetype": sourcetype,
            "event": event,
        },
        timeout=10,
        verify=True,
    )
    resp.raise_for_status()


def solarwinds_dns_failure(host: str, device: str, now: float) -> dict:
    return {
        "AlertObjectID": random.randint(10000, 99999),
        "AlertActive": True,
        "Severity": "Critical",
        "AlertMessage": f"DNS Server Unreachable on node {device}",
        "TriggeredNode": device,
        "TriggeredNodeIP": "10.42.0.15",
        "AlertDescription": (
            f"Node {device} failed to respond to DNS queries for 3 consecutive "
            f"polling cycles. Downstream resolution requests to cloud-hosted services "
            f"are timing out."
        ),
        "TriggerTimeStamp": now,
    }


def extrahop_dns_failure(host: str, device: str, now: float) -> dict:
    return {
        "id": f"dtn-{random.randint(100000, 999999)}",
        "category": "PERF",
        "title": "DNS Resolution Failures Detected",
        "risk_score": 78,
        "description": (
            f"Elevated DNS resolution failures (NXDOMAIN/timeout) observed on "
            f"on-prem relay {device}. Client requests destined for cloud-hosted "
            f"services are unable to resolve target hostnames."
        ),
        "participants": [
            {"role": "offender", "object_type": "device", "hostname": device},
            {"role": "victim", "object_type": "device", "hostname": "aws-vpc-endpoint"},
        ],
        "start_time": int(now * 1000),
        "update_time": int(now * 1000),
    }


def solarwinds_heartbeat(host: str, device: str, now: float) -> dict:
    return {
        "AlertObjectID": random.randint(10000, 99999),
        "AlertActive": False,
        "Severity": "Information",
        "AlertMessage": f"Node {device} status: Up",
        "TriggeredNode": device,
        "TriggeredNodeIP": "10.42.0.15",
        "AlertDescription": f"Routine poll: node {device} responding normally.",
        "TriggerTimeStamp": now,
    }


def extrahop_heartbeat(host: str, device: str, now: float) -> dict:
    return {
        "id": f"dtn-{random.randint(100000, 999999)}",
        "category": "PERF",
        "title": "DNS Response Times Nominal",
        "risk_score": 5,
        "description": f"DNS response times for {device} within normal range.",
        "participants": [
            {"role": "offender", "object_type": "device", "hostname": device},
        ],
        "start_time": int(now * 1000),
        "update_time": int(now * 1000),
    }


def solarwinds_lb_failure(host: str, device: str, now: float) -> dict:
    return {
        "AlertObjectID": random.randint(10000, 99999),
        "AlertActive": True,
        "Severity": "Critical",
        "AlertMessage": f"Target Group Unhealthy on {device}",
        "TriggeredNode": device,
        "TriggeredNodeIP": "10.42.0.22",
        "AlertDescription": (
            f"Load balancer {device} reports 0 of 1 registered targets healthy for "
            f"target group flight-agent-tg. Health check has failed 3 consecutive "
            f"times (HTTP 503)."
        ),
        "TriggerTimeStamp": now,
    }


def extrahop_lb_failure(host: str, device: str, now: float) -> dict:
    return {
        "id": f"dtn-{random.randint(100000, 999999)}",
        "category": "PERF",
        "title": "Elevated 5xx Error Rate at Load Balancer",
        "risk_score": 82,
        "description": (
            f"Elevated HTTP 503 response rate observed on load balancer {device}. "
            f"Backend target is failing health checks and being removed from "
            f"rotation; client requests are receiving Service Unavailable responses."
        ),
        "participants": [
            {"role": "offender", "object_type": "device", "hostname": device},
            {"role": "victim", "object_type": "device", "hostname": host},
        ],
        "start_time": int(now * 1000),
        "update_time": int(now * 1000),
    }


def solarwinds_multicloud_failure(host: str, device: str, now: float) -> dict:
    return {
        "AlertObjectID": random.randint(10000, 99999),
        "AlertActive": True,
        "Severity": "Critical",
        "AlertMessage": f"Route Propagation Failure on {device}",
        "TriggeredNode": device,
        "TriggeredNodeIP": "10.42.0.30",
        "AlertDescription": (
            f"Cross-cloud peering connection {device} reports 0 active routes "
            f"propagated for the last 5 polling cycles. Traffic destined for "
            f"peered VNet/VPC ranges is being dropped, not rejected — no ICMP "
            f"unreachable is being generated."
        ),
        "TriggerTimeStamp": now,
    }


def extrahop_multicloud_failure(host: str, device: str, now: float) -> dict:
    return {
        "id": f"dtn-{random.randint(100000, 999999)}",
        "category": "PERF",
        "title": "Cross-Cloud Peering Connection Down",
        "risk_score": 85,
        "description": (
            f"No traffic observed traversing peering connection {device} in the "
            f"last polling interval. Outbound flows toward the peered cloud "
            f"provider are timing out at the client rather than being actively "
            f"refused, consistent with a dropped route rather than a blocked port."
        ),
        "participants": [
            {"role": "offender", "object_type": "device", "hostname": device},
            {"role": "victim", "object_type": "device", "hostname": host},
        ],
        "start_time": int(now * 1000),
        "update_time": int(now * 1000),
    }


SCENARIOS = {
    "dns-failure": (solarwinds_dns_failure, extrahop_dns_failure, "Critical", "onprem-dns-relay-01"),
    "lb-failure": (solarwinds_lb_failure, extrahop_lb_failure, "Critical", "alb-travel-planner-prod"),
    "multicloud-failure": (solarwinds_multicloud_failure, extrahop_multicloud_failure, "Critical", "aws-azure-vnet-peering-01"),
    "baseline": (solarwinds_heartbeat, extrahop_heartbeat, "Information", "onprem-dns-relay-01"),
}

# Splunk's Logs view "Severity" column reads a lowercase `severity` field with
# CIM Alerts-model values (critical/high/medium/low/informational) — neither
# vendor's native field name/casing ("Severity"/"risk_score") matches that, so
# without this it shows "Unknown". Real deployments normalize onto this via
# CIM field aliasing (same purpose); we set it directly since there's no CIM
# alias config in this lab.
SEVERITY_MAP = {"Critical": "critical", "Information": "informational"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS.keys(), default="dns-failure")
    parser.add_argument("--host", required=True,
                         help="Host value to tag events with (sets the Splunk `host` "
                              "metadata field) — must match the k8s node hostname the "
                              "failing span's host.name/k8s.node.name resolve to, for the "
                              "Infrastructure host entity page's Related Content pivot.")
    parser.add_argument("--device", default=None,
                         help="Simulated device/node name referenced in the event body "
                              "(default varies by scenario: on-prem DNS relay for "
                              "dns-failure, ALB name for lb-failure, VNet/VPC peering "
                              "connection for multicloud-failure).")
    parser.add_argument("--count", type=int, default=1,
                         help="Number of event pairs (SolarWinds + ExtraHop) to emit.")
    parser.add_argument("--index", default=os.environ.get("SPLUNK_PLATFORM_INDEX", "hybrid-cloud-rca-demo"))
    parser.add_argument("--hec-url", default=os.environ.get("HEC_URL"))
    parser.add_argument("--hec-token", default=os.environ.get("HEC_TOKEN"))
    args = parser.parse_args()

    if not args.hec_url or not args.hec_token:
        raise SystemExit("HEC_URL and HEC_TOKEN are required (env vars or --hec-url/--hec-token)")

    sw_fn, eh_fn, label, default_device = SCENARIOS[args.scenario]
    device = args.device or default_device

    for i in range(args.count):
        now = time.time()
        sw_event = sw_fn(args.host, device, now)
        eh_event = eh_fn(args.host, device, now)
        sw_event["severity"] = SEVERITY_MAP[label]
        eh_event["severity"] = SEVERITY_MAP[label]

        _post_event(args.hec_url, args.hec_token, args.index, args.host,
                    "solarwinds:alert", sw_event, now)
        _post_event(args.hec_url, args.hec_token, args.index, args.host,
                    "extrahop:detection", eh_event, now)

        print(f"[{i + 1}/{args.count}] sent {label} event pair for host={args.host} "
              f"device={device}")
        print(json.dumps({"solarwinds:alert": sw_event, "extrahop:detection": eh_event}, indent=2))

        if args.count > 1:
            time.sleep(1)


if __name__ == "__main__":
    main()
