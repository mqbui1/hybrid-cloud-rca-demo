"""Mock travel tools and LLM factory shared across all agent services."""
import os
import random

DESTINATIONS = {
    "paris": {
        "country": "France",
        "highlights": ["Eiffel Tower at sunset", "Seine dinner cruise", "Day trip to Versailles"],
    },
    "tokyo": {
        "country": "Japan",
        "highlights": ["Tsukiji market food tour", "Ghibli Museum visit", "Day trip to Hakone hot springs"],
    },
    "rome": {
        "country": "Italy",
        "highlights": ["Colosseum underground tour", "Private pasta masterclass", "Sunset walk through Trastevere"],
    },
    "london": {
        "country": "UK",
        "highlights": ["Tower of London", "British Museum", "West End show"],
    },
    "new york": {
        "country": "USA",
        "highlights": ["Central Park", "Broadway show", "Brooklyn Bridge walk"],
    },
    "sydney": {
        "country": "Australia",
        "highlights": ["Opera House tour", "Bondi Beach", "Blue Mountains day trip"],
    },
}


def search_flights(origin: str, destination: str, departure: str) -> str:
    random.seed(hash((origin, destination, departure)) % (2**32))
    airline = random.choice(["SkyLine", "AeroJet", "CloudNine"])
    fare = random.randint(700, 1250)
    return (
        f"Top choice: {airline} non-stop {origin} -> {destination}, "
        f"depart {departure} 09:15, arrive same day 17:05. "
        f"Premium economy ${fare} return."
    )


def search_hotels(destination: str, check_in: str, check_out: str) -> str:
    random.seed(hash((destination, check_in, check_out)) % (2**32))
    name = random.choice(["Grand Meridian", "Hotel Lumiere", "The Atlas"])
    rate = random.randint(240, 410)
    return (
        f"{name} near the historic centre. Boutique suites, rooftop bar. "
        f"${rate}/night including breakfast."
    )


def search_activities(destination: str) -> str:
    data = DESTINATIONS.get(destination.lower(), DESTINATIONS["paris"])
    bullets = "\n".join(f"- {item}" for item in data["highlights"])
    return f"Signature experiences in {destination.title()}:\n{bullets}"


def create_llm():
    """
    Create LLM instance based on env configuration.

    LLM_PROVIDER=openai (default): uses OPENAI_API_KEY + OPENAI_BASE_URL + OPENAI_MODEL
    LLM_PROVIDER=bedrock:          uses BEDROCK_MODEL_ID + AWS credentials
    MOCK_MODE=true:                returns None (no LLM, mock tool results only)
    """
    if os.environ.get("MOCK_MODE", "false").lower() == "true":
        return None

    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    if provider == "bedrock":
        from langchain_aws import ChatBedrock
        return ChatBedrock(
            model_id=os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"
            ),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )

    # Default: OpenAI-compatible endpoint
    from langchain_openai import ChatOpenAI
    kwargs = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "api_key": os.environ.get("OPENAI_API_KEY", "none"),
        "timeout": 10,
    }
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
