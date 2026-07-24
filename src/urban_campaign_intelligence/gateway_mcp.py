"""Connect the orchestrator agent to the AgentCore Gateway over MCP, signed with SigV4.

The gateway exposes get_weather / get_events / get_mobility as governed MCP tools backed by a Lambda
(see agentcore.json and app/gateway_tools/). The runtime discovers the gateway's MCP URL from an env
var the CDK injects (AGENTCORE_GATEWAY_<NAME>_URL); calls are authenticated with the runtime's IAM
role via SigV4 (authorizerType AWS_IAM), because the gateway has no public/JWT surface here.

Everything is imported lazily so the core package stays dependency-light for non-runtime use.
"""

from __future__ import annotations

import os
from typing import Any

# Env var the CDK sets on the runtime for the in-project gateway (name "UrbanCampaignTools").
# AGENTCAMPAIGN_GATEWAY_URL overrides it for local runs against a deployed gateway.
GATEWAY_URL_ENV = "AGENTCORE_GATEWAY_URBANCAMPAIGNTOOLS_URL"
GATEWAY_SIGV4_SERVICE = "bedrock-agentcore"


def gateway_url() -> str | None:
    return os.getenv("AGENTCAMPAIGN_GATEWAY_URL") or os.getenv(GATEWAY_URL_ENV)


def _sigv4_httpx_auth(service: str, region: str) -> Any:
    """An httpx.Auth that signs each request with SigV4 using the ambient AWS credentials.

    Signs a minimal AWSRequest and copies only the signing headers back onto the httpx request, so
    httpx-managed headers (content-length, connection…) are never part of the signature.
    """
    import botocore.session
    import httpx
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    # botocore (not boto3): botocore[crt] is a runtime dependency; boto3 is not guaranteed there.
    credentials = botocore.session.get_session().get_credentials().get_frozen_credentials()
    signer = SigV4Auth(credentials, service, region)

    class _SigV4Auth(httpx.Auth):
        requires_request_body = True

        def auth_flow(self, request):  # type: ignore[override]
            aws_req = AWSRequest(method=request.method, url=str(request.url), data=request.content or b"")
            aws_req.headers["Content-Type"] = request.headers.get("content-type", "application/json")
            signer.add_auth(aws_req)
            for header in ("Authorization", "X-Amz-Date", "X-Amz-Security-Token", "X-Amz-Content-SHA256"):
                if header in aws_req.headers:
                    request.headers[header] = aws_req.headers[header]
            yield request

    return _SigV4Auth()


def build_gateway_mcp_client(url: str, region: str | None = None) -> Any:
    """A Strands MCPClient bound to the gateway MCP endpoint, SigV4-signed. Use as a context manager."""
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp import MCPClient

    resolved_region = region or os.getenv("AWS_REGION") or "us-east-1"
    auth = _sigv4_httpx_auth(GATEWAY_SIGV4_SERVICE, resolved_region)
    return MCPClient(lambda: streamablehttp_client(url, auth=auth))
