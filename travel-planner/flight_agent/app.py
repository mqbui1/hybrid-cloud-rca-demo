"""
Flight Agent — specialist for flight search.

POST /invoke: finds best flight option for origin/destination/date.
Uses LLM to format results if configured, otherwise returns mock data directly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.otel_setup import setup_otel

setup_otel("flight-agent")

import logging

from flask import Flask, jsonify, request
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from shared.tools import create_llm, search_flights

logger = logging.getLogger(__name__)
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "flight-agent"})


@app.route("/invoke", methods=["POST"])
def invoke():
    if os.environ.get("LB_UNHEALTHY", "false").lower() == "true":
        # Simulates the load balancer having marked this target unhealthy and
        # removed it from rotation (e.g. failing health checks) — the process
        # itself is up, but requests routed to it get a 503, not a
        # connection-refused/DNS error.
        logger.warning("flight-agent marked unhealthy by LB — returning 503 (simulated)")
        return jsonify({"error": "Service Temporarily Unavailable"}), 503

    payload = request.get_json(force=True) or {}
    origin = payload.get("origin", "Seattle")
    destination = payload.get("destination", "Paris")
    departure = payload.get("departure", "2026-08-01")

    logger.info("flight-agent invoked: %s → %s on %s", origin, destination, departure)
    mock_result = search_flights(origin, destination, departure)

    travellers = int(payload.get("travellers", 2))
    llm = create_llm()
    if llm is None:
        result = mock_result
    else:
        from langchain_core.messages import HumanMessage, SystemMessage
        logger.info("Calling LLM to format flight recommendation")
        try:
            response = llm.invoke([
                SystemMessage(content="You are a flight specialist. Present the flight option concisely and professionally."),
                HumanMessage(content=f"Flight data: {mock_result}\n\nPresent this as a recommendation for {travellers} travellers from {origin} to {destination} on {departure}."),
            ])
            result = response.content
            logger.info("LLM flight response received successfully")
        except Exception as e:
            logger.exception("LLM call failed in flight-agent")
            raise

    return jsonify({"result": result, "service": "flight-agent"})
