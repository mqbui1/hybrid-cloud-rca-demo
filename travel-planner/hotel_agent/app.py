"""
Hotel Agent — specialist for hotel recommendations.

POST /invoke: recommends hotel for destination/dates.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.otel_setup import setup_otel

setup_otel("hotel-agent")

import logging

from flask import Flask, jsonify, request
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from shared.tools import create_llm, search_hotels

logger = logging.getLogger(__name__)
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "hotel-agent"})


@app.route("/invoke", methods=["POST"])
def invoke():
    payload = request.get_json(force=True) or {}
    destination = payload.get("destination", "Paris")
    check_in = payload.get("check_in", "2026-08-01")
    check_out = payload.get("check_out", "2026-08-08")
    travellers = int(payload.get("travellers", 2))

    logger.info("hotel-agent invoked: %s, check-in %s, check-out %s", destination, check_in, check_out)
    mock_result = search_hotels(destination, check_in, check_out)

    llm = create_llm()
    if llm is None:
        result = mock_result
    else:
        from langchain_core.messages import HumanMessage, SystemMessage
        logger.info("Calling LLM to format hotel recommendation")
        try:
            response = llm.invoke([
                SystemMessage(content="You are a hotel specialist. Present the hotel recommendation concisely and professionally."),
                HumanMessage(content=f"Hotel data: {mock_result}\n\nPresent this as a recommendation for {travellers} travellers in {destination} from {check_in} to {check_out}."),
            ])
            result = response.content
            logger.info("LLM hotel response received successfully")
        except Exception as e:
            logger.exception("LLM call failed in hotel-agent")
            raise

    return jsonify({"result": result, "service": "hotel-agent"})
