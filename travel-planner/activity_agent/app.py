"""
Activity Agent — specialist for destination experiences.

POST /invoke: curates activities and experiences for a destination.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.otel_setup import setup_otel

setup_otel("activity-agent")

import logging

from flask import Flask, jsonify, request
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from shared.tools import create_llm, search_activities

logger = logging.getLogger(__name__)
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "activity-agent"})


@app.route("/invoke", methods=["POST"])
def invoke():
    payload = request.get_json(force=True) or {}
    destination = payload.get("destination", "Paris")
    travellers = int(payload.get("travellers", 2))

    logger.info("activity-agent invoked: destination=%s", destination)
    mock_result = search_activities(destination)

    llm = create_llm()
    if llm is None:
        result = mock_result
    else:
        from langchain_core.messages import HumanMessage, SystemMessage
        logger.info("Calling LLM to curate activity recommendations")
        try:
            response = llm.invoke([
                SystemMessage(content="You are an activity specialist. Curate and present experiences engagingly."),
                HumanMessage(content=f"Available experiences: {mock_result}\n\nPresent these as curated recommendations for {travellers} travellers spending a week in {destination}."),
            ])
            result = response.content
            logger.info("LLM activity response received successfully")
        except Exception as e:
            logger.exception("LLM call failed in activity-agent")
            raise

    return jsonify({"result": result, "service": "activity-agent"})
