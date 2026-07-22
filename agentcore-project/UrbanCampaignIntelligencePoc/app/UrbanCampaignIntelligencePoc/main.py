"""AgentCore Runtime entrypoint for Urban Campaign Intelligence.

This is the single canonical entrypoint (agentcore.json -> entrypoint: main.py). It is a
thin transport wrapper: it maps the InvokeAgentRuntime payload to the shared business
pipeline and returns the recommendation as JSON.

    InvokeAgentRuntime -> invoke() -> handle_invocation -> deterministic core -> JSON

The business logic lives in the installable ``urban_campaign_intelligence`` package, imported
here rather than copied, so the CLI, the tests and this runtime all run the same code. With no
Bedrock model configured the pipeline degrades to deterministic heuristics, so this vertical is
exercisable locally (``python main.py`` then curl) without AWS.

Packaging note: the package must be present in the deployed CodeZip. Locally it is resolved via
``pip install -e .`` at the repo root; the deployment strategy (build-time copy vs private
index) is an open decision tracked in ARCHITECTURE.md §12.2.
"""

from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from urban_campaign_intelligence.invocation import handle_invocation


def build_app(debug: bool = False) -> BedrockAgentCoreApp:
    """Construct the runtime app with the business entrypoint attached.

    ``debug=True`` surfaces the uvicorn startup and access logs the SDK otherwise silences.
    """
    app = BedrockAgentCoreApp(debug=debug)

    @app.entrypoint
    def invoke(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
        # Deterministic request/response: return JSON, not a stream. The correlation id is
        # inside the response under result["run"]["run_id"].
        return handle_invocation(payload)

    return app


app = build_app()


if __name__ == "__main__":
    import os

    # AgentCore serves on 8080 in production; PORT lets a local run pick a free port, since
    # the SDK does not read it. DEBUG=1 surfaces the startup logs.
    debug = os.getenv("DEBUG", "").lower() in {"1", "true", "yes"}
    build_app(debug=debug).run(port=int(os.getenv("PORT", "8080")))
