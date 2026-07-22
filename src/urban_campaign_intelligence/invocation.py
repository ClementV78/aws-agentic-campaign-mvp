"""Pure payload -> recommendation mapping, shared by every runtime front-end.

This is the seam between a transport (the AgentCore entrypoint in app/main.py, the local
CLI, a test) and the business pipeline. It stays in the shared package so it is unit-tested
once and reused everywhere; the AgentCore-specific wrapper lives in app/main.py.
"""

from __future__ import annotations

from typing import Any

from urban_campaign_intelligence.local_agent import LocalRequestMapper, UrbanCampaignStrandsAgent

_agent = UrbanCampaignStrandsAgent()


def handle_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an InvokeAgentRuntime payload to a recommendation response.

    Payload shape mirrors the local CLI contract: ``{"scenario_id": ...}`` for replay,
    ``{"datetime": ..., "city": ...}`` for a live request. A payload carrying neither
    raises ValueError, which the runtime surfaces as a 4xx.

    Needs no Bedrock: with no model provider configured every LLM step degrades to its
    deterministic heuristic, so the whole vertical runs offline. The response carries its
    correlation id under ``result["run"]["run_id"]``.
    """
    request = LocalRequestMapper.from_dict(payload or {})
    return _agent.handle_request(request)
