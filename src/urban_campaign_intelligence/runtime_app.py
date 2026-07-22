"""AgentCore Runtime entrypoint wired to the deterministic business pipeline.

This is the first closed vertical of the DAT (ARCHITECTURE.md §12.2):

    InvokeAgentRuntime -> this entrypoint -> UrbanCampaignApplicationService
        -> deterministic core -> explainable JSON response

It runs locally through ``app.run()`` (port 8080) and needs no Bedrock: with no model
provider configured, every LLM step degrades to its deterministic heuristic, so the whole
vertical is exercisable offline. The Strands agentic loop that will drive tool calls on top
of this pipeline is the next step, gated on the account-level Bedrock unblock.

``handle_invocation`` is the pure mapping payload -> request -> response and is unit-tested
directly. ``bedrock_agentcore`` is imported lazily so importing this module — and running the
test suite — does not require the runtime SDK to be installed.
"""

from __future__ import annotations

import os
from typing import Any

from urban_campaign_intelligence.local_agent import LocalRequestMapper, UrbanCampaignStrandsAgent

_agent = UrbanCampaignStrandsAgent()


def handle_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Map an InvokeAgentRuntime payload to a recommendation response.

    Payload shape mirrors the local CLI contract: ``{"scenario_id": ...}`` for replay,
    ``{"datetime": ..., "city": ...}`` for a live request. A payload carrying neither
    raises ValueError, surfaced to the caller as a 4xx by the runtime.
    """
    request = LocalRequestMapper.from_dict(payload or {})
    return _agent.handle_request(request)


def build_app() -> Any:
    """Construct the BedrockAgentCoreApp with the business entrypoint attached.

    Imported lazily: the runtime SDK is only needed to actually serve, not to map requests.
    """
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
        # The correlation id is carried inside the response under result["run"]["run_id"].
        return handle_invocation(payload)

    return app


if __name__ == "__main__":
    # AgentCore serves on 8080 in production; PORT lets a local run pick a free one,
    # since the SDK does not read it itself.
    build_app().run(port=int(os.getenv("PORT", "8080")))
