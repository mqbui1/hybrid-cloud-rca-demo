"""
Currency Agent — specialist for exchange-rate lookups.

Deliberately deployed as "the second cloud" in this demo (see
CLOUD_PROVIDER/CLOUD_REGION in its k8s manifest) — the orchestrator calling
this agent stands in for a transaction that has to cross from one cloud
provider to another, not just on-prem-to-cloud.

POST /invoke: returns the current exchange rate for a destination.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.otel_setup import setup_otel

setup_otel("currency-agent")

import logging

from flask import Flask, jsonify, request
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from shared.tools import get_exchange_rate

logger = logging.getLogger(__name__)
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "currency-agent"})


@app.route("/invoke", methods=["POST"])
def invoke():
    if os.environ.get("CROSS_CLOUD_UNREACHABLE", "false").lower() == "true":
        # Simulates a broken cross-cloud network path (e.g. VPC peering /
        # ExpressRoute connectivity down): unlike DNS failure (immediate
        # resolution error) or an LB health-check failure (immediate clean
        # 503), a dropped cross-cloud route produces no response at all —
        # the caller just waits until its own timeout fires.
        logger.warning("currency-agent unreachable — simulating dropped cross-cloud route (will hang)")
        time.sleep(30)

    payload = request.get_json(force=True) or {}
    destination = payload.get("destination", "Paris")

    logger.info("currency-agent invoked: destination=%s", destination)
    result = get_exchange_rate(destination)

    return jsonify({"result": result, "service": "currency-agent"})
