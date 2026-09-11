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

Usage:
  export HEC_URL=https://<stack>.splunkcloud.com:8088
  export HEC_TOKEN=<hec-token>
  python3 generate_events.py --scenario dns-failure --host <k8s-node-hostname>
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


def solarwinds_dns_failure(host: str, relay_node: str, now: float) -> dict:
    return {
        "AlertObjectID": random.randint(10000, 99999),
        "AlertActive": True,
        "Severity": "Critical",
        "AlertMessage": f"DNS Server Unreachable on node {relay_node}",
        "TriggeredNode": relay_node,
        "TriggeredNodeIP": "10.42.0.15",
        "AlertDescription": (
            f"Node {relay_node} failed to respond to DNS queries for 3 consecutive "
            f"polling cycles. Downstream resolution requests to cloud-hosted services "
            f"are timing out."
        ),
        "TriggerTimeStamp": now,
    }


def extrahop_dns_failure(host: str, relay_node: str, now: float) -> dict:
    return {
        "id": f"dtn-{random.randint(100000, 999999)}",
        "category": "PERF",
        "title": "DNS Resolution Failures Detected",
        "risk_score": 78,
        "description": (
            f"Elevated DNS resolution failures (NXDOMAIN/timeout) observed on "
            f"on-prem relay {relay_node}. Client requests destined for cloud-hosted "
            f"services are unable to resolve target hostnames."
        ),
        "participants": [
            {"role": "offender", "object_type": "device", "hostname": relay_node},
            {"role": "victim", "object_type": "device", "hostname": "aws-vpc-endpoint"},
        ],
        "start_time": int(now * 1000),
        "update_time": int(now * 1000),
    }


def solarwinds_heartbeat(host: str, relay_node: str, now: float) -> dict:
    return {
        "AlertObjectID": random.randint(10000, 99999),
        "AlertActive": False,
        "Severity": "Information",
        "AlertMessage": f"Node {relay_node} status: Up",
        "TriggeredNode": relay_node,
        "TriggeredNodeIP": "10.42.0.15",
        "AlertDescription": f"Routine poll: node {relay_node} responding normally.",
        "TriggerTimeStamp": now,
    }


def extrahop_heartbeat(host: str, relay_node: str, now: float) -> dict:
    return {
        "id": f"dtn-{random.randint(100000, 999999)}",
        "category": "PERF",
        "title": "DNS Response Times Nominal",
        "risk_score": 5,
        "description": f"DNS response times for {relay_node} within normal range.",
        "participants": [
            {"role": "offender", "object_type": "device", "hostname": relay_node},
        ],
        "start_time": int(now * 1000),
        "update_time": int(now * 1000),
    }


SCENARIOS = {
    "dns-failure": (solarwinds_dns_failure, extrahop_dns_failure, "Critical"),
    "baseline": (solarwinds_heartbeat, extrahop_heartbeat, "Information"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS.keys(), default="dns-failure")
    parser.add_argument("--host", required=True,
                         help="Host value to tag events with — must match the host "
                              "dimension on the correlated APM span/trace for the "
                              "Log Observer Connect pivot to resolve.")
    parser.add_argument("--relay-node", default="onprem-dns-relay-01",
                         help="Simulated on-prem device/node name referenced in the event body.")
    parser.add_argument("--count", type=int, default=1,
                         help="Number of event pairs (SolarWinds + ExtraHop) to emit.")
    parser.add_argument("--index", default=os.environ.get("SPLUNK_PLATFORM_INDEX", "hybrid-cloud-rca-demo"))
    parser.add_argument("--hec-url", default=os.environ.get("HEC_URL"))
    parser.add_argument("--hec-token", default=os.environ.get("HEC_TOKEN"))
    args = parser.parse_args()

    if not args.hec_url or not args.hec_token:
        raise SystemExit("HEC_URL and HEC_TOKEN are required (env vars or --hec-url/--hec-token)")

    sw_fn, eh_fn, label = SCENARIOS[args.scenario]

    for i in range(args.count):
        now = time.time()
        sw_event = sw_fn(args.host, args.relay_node, now)
        eh_event = eh_fn(args.host, args.relay_node, now)

        _post_event(args.hec_url, args.hec_token, args.index, args.host,
                    "solarwinds:alert", sw_event, now)
        _post_event(args.hec_url, args.hec_token, args.index, args.host,
                    "extrahop:detection", eh_event, now)

        print(f"[{i + 1}/{args.count}] sent {label} event pair for host={args.host} "
              f"relay_node={args.relay_node}")
        print(json.dumps({"solarwinds:alert": sw_event, "extrahop:detection": eh_event}, indent=2))

        if args.count > 1:
            time.sleep(1)


if __name__ == "__main__":
    main()
