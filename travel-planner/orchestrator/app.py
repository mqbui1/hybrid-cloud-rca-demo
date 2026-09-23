"""
Orchestrator service — entry point for travel planning.

Receives POST /plan, calls each specialist agent via HTTP in sequence,
then calls the synthesizer. OTel trace context is propagated automatically
by RequestsInstrumentor (W3C TraceContext headers), so all agent spans
appear as children of this root span in Splunk APM.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.otel_setup import setup_otel

setup_otel("orchestrator")

from datetime import datetime, timedelta

import logging

import requests
from flask import Flask, jsonify, request
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace import SpanKind, StatusCode, format_trace_id

logger = logging.getLogger(__name__)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

# Service URLs — use K8s ClusterIP DNS names, overridable via env
FLIGHT_AGENT_URL   = os.environ.get("FLIGHT_AGENT_URL",   "http://flight-agent.travel-planner.svc.cluster.local:8080")
HOTEL_AGENT_URL    = os.environ.get("HOTEL_AGENT_URL",    "http://hotel-agent.travel-planner.svc.cluster.local:8080")
ACTIVITY_AGENT_URL = os.environ.get("ACTIVITY_AGENT_URL", "http://activity-agent.travel-planner.svc.cluster.local:8080")
CURRENCY_AGENT_URL = os.environ.get("CURRENCY_AGENT_URL", "http://currency-agent.travel-planner.svc.cluster.local:8080")
SYNTHESIZER_URL    = os.environ.get("SYNTHESIZER_URL",    "http://synthesizer.travel-planner.svc.cluster.local:8080")

tracer = trace.get_tracer(__name__)


def _dates_from_now(days_out: int = 30, duration: int = 7):
    start = datetime.now() + timedelta(days=days_out)
    end = start + timedelta(days=duration)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _call_agent(agent_key: str, url: str, payload: dict, timeout: int = 30):
    with tracer.start_as_current_span(f"agent.call.{agent_key}", kind=SpanKind.CLIENT) as span:
        span.set_attribute("agent.name", agent_key)

        logger.info("Calling agent %s at %s", agent_key, url)
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            span.set_attribute("http.status_code", resp.status_code)
            logger.info("Agent %s responded successfully (HTTP %s)", agent_key, resp.status_code)
            return resp.json().get("result", "")
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            logger.exception("Agent call failed: %s", agent_key)
            raise


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "orchestrator"})


@app.route("/plan", methods=["POST"])
def plan():
    payload = request.get_json(force=True) or {}
    origin      = payload.get("origin", "Seattle")
    destination = payload.get("destination", "Paris")
    travellers  = int(payload.get("travellers", 2))
    departure, return_date = _dates_from_now()

    with tracer.start_as_current_span("travel.plan", kind=SpanKind.SERVER) as span:
        trace_id = format_trace_id(span.get_span_context().trace_id)
        span.set_attribute("travel.origin", origin)
        span.set_attribute("travel.destination", destination)
        span.set_attribute("travel.travellers", travellers)
        span.set_attribute("travel.departure", departure)

        logger.info(
            "travel.plan started: %s → %s, %d traveller(s), depart %s",
            origin, destination, travellers, departure,
        )
        errors = []

        try:
            flight_result = _call_agent("flight-agent", f"{FLIGHT_AGENT_URL}/invoke",
                {"origin": origin, "destination": destination, "departure": departure})
        except Exception as e:
            flight_result = "Flight info unavailable"
            errors.append(f"flight-agent: {e}")

        try:
            hotel_result = _call_agent("hotel-agent", f"{HOTEL_AGENT_URL}/invoke",
                {"destination": destination, "check_in": departure, "check_out": return_date})
        except Exception as e:
            hotel_result = "Hotel info unavailable"
            errors.append(f"hotel-agent: {e}")

        try:
            activity_result = _call_agent("activity-agent", f"{ACTIVITY_AGENT_URL}/invoke",
                {"destination": destination})
        except Exception as e:
            activity_result = "Activity info unavailable"
            errors.append(f"activity-agent: {e}")

        try:
            # Short timeout: currency-agent is deployed as "the second cloud"
            # in this demo (see manifests/travel-planner/currency-agent.yaml),
            # so a cross-cloud connectivity failure here should surface
            # quickly rather than blocking the whole trace for a long time.
            currency_result = _call_agent("currency-agent", f"{CURRENCY_AGENT_URL}/invoke",
                {"destination": destination}, timeout=5)
        except Exception as e:
            currency_result = "Currency info unavailable"
            errors.append(f"currency-agent: {e}")

        try:
            itinerary = _call_agent("synthesizer", f"{SYNTHESIZER_URL}/invoke", {
                "origin": origin, "destination": destination,
                "departure": departure, "return_date": return_date,
                "travellers": travellers, "flight_summary": flight_result,
                "hotel_summary": hotel_result, "activities_summary": activity_result,
                "currency_summary": currency_result,
            }, timeout=60)
        except Exception as e:
            itinerary = f"Synthesis failed: {e}"
            errors.append(f"synthesizer: {e}")

        if errors:
            span.set_attribute("travel.errors", ", ".join(errors))
            logger.warning("travel.plan completed with errors: %s", ", ".join(errors))
        else:
            logger.info("travel.plan completed successfully: %s → %s", origin, destination)

        return jsonify({
            "origin": origin, "destination": destination,
            "departure": departure, "return_date": return_date,
            "travellers": travellers, "flight_summary": flight_result,
            "hotel_summary": hotel_result, "activities_summary": activity_result,
            "currency_summary": currency_result,
            "itinerary": itinerary,
            "trace_id": trace_id,
        })
