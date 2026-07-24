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

from urban_campaign_intelligence.context_agents import EVENT_MAPPINGS
from urban_campaign_intelligence.data_access import load_advertisers
from urban_campaign_intelligence.gateway_tools import GatewayProvider

# Nova Lite: reliable tool use, cheap. Gemma was tested and rejected (no reliable tool use).
ORCHESTRATOR_MODEL = "amazon.nova-lite-v1:0"

# The signals the deterministic pipeline needs. Once the collector holds all of them the agent has
# done its job, so the next model turn (a summary we discard) is cancelled — see run_prompt.
_REQUIRED_SIGNALS = frozenset({"city", "datetime", "weather", "events", "mobility"})

_SYSTEM_PROMPT = (
    "You gather context for an urban ad-campaign recommendation. From the user's request, "
    "determine the city and the datetime, then call get_weather, get_events and get_mobility once "
    "each to collect the signals for that city and time. Pass city and an ISO 8601 datetime to each. "
    "\n\n"
    "The campaign can run for one advertiser (single-brand) or across all of them (multi-brand). "
    "The known advertisers are: {roster}. If — and only if — the request clearly targets one of "
    "these advertisers, call set_campaign_focus once with that advertiser's exact name; the "
    "deterministic allocator will then favour it while still leaving billboards to the others. If "
    "the request names no specific advertiser, do not call set_campaign_focus (multi-brand). "
    "\n\n"
    "Once the signals are gathered, stop and confirm briefly."
)


def run_prompt(
    prompt: str, *, model_id: str | None = None, region_name: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the Strands orchestrator on a natural-language prompt.

    Returns ``(context, meta)``. ``context`` holds the collected signals: ``city``, ``datetime``
    and the three signal payloads (``weather``, ``events``, ``mobility``). ``meta`` holds the
    orchestration cost — ``model_id`` and the Bedrock token usage — so the caller can put this
    LLM round-trip on the run trace (it runs before the deterministic pipeline). Raises ValueError
    if the agent did not gather the full context.
    """
    from strands import Agent, tool
    from strands.hooks import BeforeModelCallEvent, HookProvider, HookRegistry
    from strands.models import BedrockModel

    collector: dict[str, Any] = {}
    provider = GatewayProvider()
    # The agent decides mono vs multi-brand; give it the roster and let it resolve a named brand
    # to the canonical advertiser. Unknown names are ignored (treated as multi-brand) rather than
    # acted on, so a hallucinated brand cannot skew the allocation.
    advertisers_by_name = {a["name"].lower(): a["name"] for a in load_advertisers()}

    @tool
    def get_weather(city: str, datetime_iso: str) -> str:
        """Get weather signals for a city at an ISO 8601 datetime."""
        payload = provider.get_weather(city=city, datetime_iso=datetime_iso)
        collector["city"], collector["datetime"], collector["weather"] = city, datetime_iso, payload
        return json.dumps(payload, default=str)

    @tool
    def get_events(city: str, datetime_iso: str) -> str:
        """Get urban events for a city at an ISO 8601 datetime."""
        # Pass the known event types, like the live path does: without them the provider has
        # nothing to look up and returns an empty list, so the agent would always see no events.
        payload = provider.get_events(city=city, datetime_iso=datetime_iso, event_types=list(EVENT_MAPPINGS.keys()))
        collector["events"] = payload
        return json.dumps(payload, default=str)

    @tool
    def get_mobility(city: str, datetime_iso: str) -> str:
        """Get mobility signals for a city at an ISO 8601 datetime."""
        payload = provider.get_mobility(city=city, datetime_iso=datetime_iso)
        collector["mobility"] = payload
        return json.dumps(payload, default=str)

    @tool
    def set_campaign_focus(advertiser: str) -> str:
        """Focus the campaign on one advertiser. Call only when the request targets a single brand."""
        canonical = advertisers_by_name.get(advertiser.strip().lower())
        if canonical is None:
            return f"Unknown advertiser '{advertiser}'; ignoring, campaign stays multi-brand."
        collector["focus_advertiser"] = canonical
        return f"Campaign focused on {canonical} (allocation stays proportional to other brands)."

    class _StopWhenGathered(HookProvider):
        """Cancel the model turn as soon as every required signal is collected.

        The agent only needs to gather context; once the collector holds all signals, the loop's
        next model call would just produce a summary we discard. Cancelling it removes that turn —
        model-agnostic (it fires on actual completeness, not a fixed turn count, so a model that
        gathers over several cycles still works) and saves a full model round-trip in latency/tokens.
        """

        def register_hooks(self, registry: HookRegistry) -> None:
            registry.add_callback(BeforeModelCallEvent, self._cancel_when_gathered)

        def _cancel_when_gathered(self, event: BeforeModelCallEvent) -> None:
            if _REQUIRED_SIGNALS <= collector.keys():
                event.cancel = "Context gathered; the final model turn is not needed."

    resolved_model_id = model_id or os.getenv("AGENTCAMPAIGN_BEDROCK_MODEL_ID") or ORCHESTRATOR_MODEL
    model = BedrockModel(model_id=resolved_model_id, region_name=region_name or os.getenv("AWS_REGION"))
    system_prompt = _SYSTEM_PROMPT.format(roster=", ".join(advertisers_by_name.values()))
    agent = Agent(
        model=model,
        tools=[get_weather, get_events, get_mobility, set_campaign_focus],
        system_prompt=system_prompt,
        hooks=[_StopWhenGathered()],
    )
    result = agent(f"Current datetime is {datetime.now().isoformat()}. Request: {prompt}")

    missing = _REQUIRED_SIGNALS - collector.keys()
    if missing:
        raise ValueError(f"Orchestrator did not gather full context; missing: {sorted(missing)}")
    # No per-tool timings here: on the deployed runtime AgentCore already traces each tool call and
    # the token usage natively (X-Ray GenAI). We keep only model_id + usage as a coarse summary for
    # the local trace, where no AWS tracer exists.
    return collector, {"model_id": resolved_model_id, **_usage(result)}


def _usage(result: Any) -> dict[str, Any]:
    """Pull the Bedrock token usage off the Strands AgentResult, tolerant of shape changes."""
    usage = getattr(getattr(result, "metrics", None), "accumulated_usage", None) or {}
    return {
        "input_tokens": usage.get("inputTokens"),
        "output_tokens": usage.get("outputTokens"),
        "total_tokens": usage.get("totalTokens"),
    }
