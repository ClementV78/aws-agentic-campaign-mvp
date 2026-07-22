"""Agentic orchestration of context gathering (target mode: prompt).

A real Strands agent that, given a natural-language prompt, decides the city and datetime and
calls the context tools to collect the signals. This is the "the LLM decides the tool calls" of
ARCHITECTURE.md §5.1.2 — the orchestration layer above the deterministic core.

The agent only orchestrates the input (interpret the prompt, call the tools). The scoring stays
deterministic and outside the agent (ADR-002): run_prompt returns the collected signals, and the
caller feeds them to the same deterministic pipeline the structured modes use.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from urban_campaign_intelligence.gateway_tools import GatewayProvider

# Nova Lite: reliable tool use, cheap. Gemma was tested and rejected (no reliable tool use).
ORCHESTRATOR_MODEL = "amazon.nova-lite-v1:0"

_SYSTEM_PROMPT = (
    "You gather context for an urban ad-campaign recommendation. From the user's request, "
    "determine the city and the datetime, then call every available tool once to collect the "
    "weather, events and mobility signals for that city and time. Pass city and an ISO 8601 "
    "datetime to each tool. Once all three tools have returned, stop and confirm briefly."
)


def run_prompt(prompt: str, *, model_id: str | None = None, region_name: str | None = None) -> dict[str, Any]:
    """Run the Strands orchestrator on a natural-language prompt.

    Returns the collected context: ``city``, ``datetime`` and the three signal payloads
    (``weather``, ``events``, ``mobility``). Raises ValueError if the agent did not gather them.
    """
    from strands import Agent, tool
    from strands.models import BedrockModel

    collector: dict[str, Any] = {}
    provider = GatewayProvider()

    @tool
    def get_weather(city: str, datetime_iso: str) -> str:
        """Get weather signals for a city at an ISO 8601 datetime."""
        payload = provider.get_weather(city=city, datetime_iso=datetime_iso)
        collector["city"], collector["datetime"], collector["weather"] = city, datetime_iso, payload
        return json.dumps(payload, default=str)

    @tool
    def get_events(city: str, datetime_iso: str) -> str:
        """Get urban events for a city at an ISO 8601 datetime."""
        payload = provider.get_events(city=city, datetime_iso=datetime_iso)
        collector["events"] = payload
        return json.dumps(payload, default=str)

    @tool
    def get_mobility(city: str, datetime_iso: str) -> str:
        """Get mobility signals for a city at an ISO 8601 datetime."""
        payload = provider.get_mobility(city=city, datetime_iso=datetime_iso)
        collector["mobility"] = payload
        return json.dumps(payload, default=str)

    model = BedrockModel(
        model_id=model_id or os.getenv("AGENTCAMPAIGN_BEDROCK_MODEL_ID") or ORCHESTRATOR_MODEL,
        region_name=region_name or os.getenv("AWS_REGION"),
    )
    agent = Agent(model=model, tools=[get_weather, get_events, get_mobility], system_prompt=_SYSTEM_PROMPT)
    agent(f"Current datetime is {datetime.now().isoformat()}. Request: {prompt}")

    missing = {"city", "datetime", "weather", "events", "mobility"} - collector.keys()
    if missing:
        raise ValueError(f"Orchestrator did not gather full context; missing: {sorted(missing)}")
    return collector
