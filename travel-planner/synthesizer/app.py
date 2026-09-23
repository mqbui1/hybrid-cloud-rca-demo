"""
Synthesizer — combines all specialist outputs into a final itinerary.

POST /invoke: takes flight/hotel/activities summaries and produces a
structured day-by-day travel itinerary using the LLM.
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.otel_setup import setup_otel

setup_otel("synthesizer")

from flask import Flask, jsonify, request
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from shared.tools import create_llm

logger = logging.getLogger(__name__)
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "synthesizer"})


@app.route("/invoke", methods=["POST"])
def invoke():
    payload = request.get_json(force=True) or {}
    origin = payload.get("origin", "Seattle")
    destination = payload.get("destination", "Paris")
    departure = payload.get("departure", "2026-08-01")
    return_date = payload.get("return_date", "2026-08-08")
    travellers = int(payload.get("travellers", 2))
    flight_summary = payload.get("flight_summary", "")
    hotel_summary = payload.get("hotel_summary", "")
    activities_summary = payload.get("activities_summary", "")
    currency_summary = payload.get("currency_summary", "")

    logger.info(
        "synthesizer invoked: %s → %s, %s to %s, %d traveller(s)",
        origin, destination, departure, return_date, travellers,
    )
    llm = create_llm()
    if llm is None:
        result = (
            f"7-Day {destination} Itinerary for {travellers} travellers\n"
            f"Flights: {flight_summary}\n"
            f"Hotel: {hotel_summary}\n"
            f"Activities: {activities_summary}\n"
            f"Currency: {currency_summary}"
        )
    else:
        from langchain_core.messages import HumanMessage, SystemMessage
        specialist_data = json.dumps(
            {"flight": flight_summary, "hotel": hotel_summary, "activities": activities_summary,
             "currency": currency_summary},
            indent=2,
        )
        logger.info("Calling LLM to synthesize final itinerary")
        try:
            response = llm.invoke([
                SystemMessage(
                    content=(
                        "You are a travel plan synthesizer. Combine the specialist summaries into a "
                        "concise, structured 7-day itinerary with day-by-day highlights. Be warm and engaging."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Trip: {origin} to {destination}, {departure} to {return_date}, {travellers} travellers.\n\n"
                        f"Specialist summaries:\n{specialist_data}"
                    )
                ),
            ])
            result = response.content
            logger.info("LLM synthesis completed successfully")
        except Exception as e:
            logger.exception("LLM synthesis failed")
            raise

    return jsonify({"result": result, "service": "synthesizer"})
