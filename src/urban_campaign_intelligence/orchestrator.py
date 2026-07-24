"""Agentic orchestration of context gathering (target mode: prompt).

A real Strands agent that, given a natural-language prompt, decides the city and datetime and calls
the context tools to collect the signals. This is the "the LLM decides the tool calls" of
ARCHITECTURE.md §5.1.2 — the orchestration layer above the deterministic core.

The three context tools (get_weather / get_events / get_mobility) are consumed through the
**AgentCore Gateway** over MCP (SigV4), not in-process: their logic runs in a governed Lambda behind
the gateway. Because those results now return to the agent (not to our code), an AfterToolCallEvent
hook captures each one into the collector. set_campaign_focus stays a local tool (it interprets the
prompt, it is not a context source). The scoring stays deterministic and outside the agent (ADR-002).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from urban_campaign_intelligence.data_access import load_advertisers
from urban_campaign_intelligence.gateway_mcp import build_gateway_mcp_client, gateway_url

# Nova Lite: reliable tool use, cheap. Gemma was tested and rejected (no reliable tool use).
ORCHESTRATOR_MODEL = "amazon.nova-lite-v1:0"

# The signals the deterministic pipeline needs. Once the collector holds all of them the agent has
# done its job, so the next model turn (a summary we discard) is cancelled — see run_prompt.
_REQUIRED_SIGNALS = frozenset({"city", "datetime", "weather", "events", "mobility"})

_SYSTEM_PROMPT = (
    "You gather context for an urban ad-campaign recommendation. From the user's request, "
    "determine the city and the datetime, then call each of the available context tools once "
    "(weather, events, mobility) to collect the signals for that city and time. Pass city and an "
    "ISO 8601 datetime to each. "
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
    from strands.hooks import AfterToolCallEvent, BeforeModelCallEvent, HookProvider, HookRegistry
    from strands.models import BedrockModel

    url = gateway_url()
    if not url:
        raise RuntimeError(
            "AgentCore Gateway MCP URL not found. Expected env AGENTCORE_GATEWAY_URBANCAMPAIGNTOOLS_URL "
            "(injected on the deployed runtime) or AGENTCAMPAIGN_GATEWAY_URL for a local run."
        )

    collector: dict[str, Any] = {}
    # The agent decides mono vs multi-brand; give it the roster and let it resolve a named brand
    # to the canonical advertiser. Unknown names are ignored (treated as multi-brand) rather than
    # acted on, so a hallucinated brand cannot skew the allocation.
    advertisers_by_name = {a["name"].lower(): a["name"] for a in load_advertisers()}

    @tool
    def set_campaign_focus(advertiser: str) -> str:
        """Focus the campaign on one advertiser. Call only when the request targets a single brand."""
        canonical = advertisers_by_name.get(advertiser.strip().lower())
        if canonical is None:
            return f"Unknown advertiser '{advertiser}'; ignoring, campaign stays multi-brand."
        collector["focus_advertiser"] = canonical
        return f"Campaign focused on {canonical} (allocation stays proportional to other brands)."

    class _CaptureSignals(HookProvider):
        """Store each gateway tool's result in the collector (post-tool).

        The context tools now run behind the Gateway (Lambda), so their results return to the agent
        instead of to our code. This hook intercepts them — the hook-based equivalent of the old
        in-process collector. The Lambda payloads carry city/datetime, so we read them from there.
        """

        def register_hooks(self, registry: HookRegistry) -> None:
            registry.add_callback(AfterToolCallEvent, self._capture)

        def _capture(self, event: AfterToolCallEvent) -> None:
            name = (event.tool_use or {}).get("name", "")
            try:
                payload = json.loads(event.result["content"][0]["text"])
            except (KeyError, IndexError, TypeError, ValueError):
                return  # non-JSON tool result (e.g. set_campaign_focus) — nothing to capture here
            if name.endswith("get_weather"):
                collector["weather"], collector["city"], collector["datetime"] = (
                    payload, payload.get("city"), payload.get("datetime"))
            elif name.endswith("get_events"):
                collector["events"] = payload
            elif name.endswith("get_mobility"):
                collector["mobility"] = payload

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

    # The context tools come from the Gateway (MCP, SigV4); set_campaign_focus stays local. The MCP
    # session must stay open for the whole agent run, hence the context manager.
    mcp_client = build_gateway_mcp_client(url, region=region_name or os.getenv("AWS_REGION"))
    with mcp_client:
        gateway_tools = [t for t in mcp_client.list_tools_sync() if t.tool_name.startswith("contextTools")]
        agent = Agent(
            model=model,
            tools=[*gateway_tools, set_campaign_focus],
            system_prompt=system_prompt,
            hooks=[_CaptureSignals(), _StopWhenGathered()],
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
