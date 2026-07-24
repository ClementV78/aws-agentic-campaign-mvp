"""AgentCore Gateway Lambda target: exposes get_weather / get_events / get_mobility as MCP tools.

The gateway routes each tool call to this Lambda. The tool name is carried on the invocation
context (client_context), the arguments in the event. We dispatch to the shared GatewayProvider —
the same provider logic the local runtime used to call in-process — so the business behaviour is
unchanged; only the transport (in-process -> Gateway/MCP -> Lambda) differs.

gateway_tools.py is pure-stdlib (urllib only) and is staged next to this file at build time by
scripts/deploy.sh, so the Lambda has no third-party dependency.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import gateway_tools

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# The event types the live path queries (keys of context_agents.EVENT_MAPPINGS). Hardcoded here so
# the Lambda stays self-contained with only the stdlib-pure gateway_tools.py — no need to stage the
# heavier context_agents module. Keep in sync with EVENT_MAPPINGS.
_EVENT_TYPES = ["major_concert", "fashion_event", "sports_event", "family_event"]

# Real backends, forced in code: the Gateway Lambda compute config has no envVars field, so the
# usual WEATHER_PROVIDER/... env selection is unavailable here. Each real provider keeps its own
# mock fallback on failure, so a slow/unreachable upstream degrades instead of erroring.
_provider = gateway_tools.GatewayProvider(
    weather_provider_mode="open_meteo",
    events_provider_mode="paris_open_data",
    mobility_provider_mode="forecast",
)


def _tool_name(event: dict[str, Any], context: Any) -> str:
    """Resolve which tool was invoked.

    AgentCore Gateway carries the tool name on the Lambda client context. The exact key is
    version-sensitive, so we probe the documented location and fall back to scanning the custom
    context / event; the raw shapes are logged on every call so CloudWatch reveals the real contract.
    """
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    for key in ("bedrockAgentCoreToolName", "bedrockagentcoreToolName", "toolName"):
        if custom.get(key):
            return str(custom[key])
    # Some setups pass the tool name in the event envelope instead.
    for key in ("toolName", "name", "__tool_name__"):
        if isinstance(event, dict) and event.get(key):
            return str(event[key])
    return ""


def _arguments(event: dict[str, Any]) -> dict[str, Any]:
    """The tool arguments. Gateway may pass them raw or wrapped under a key."""
    if isinstance(event, dict):
        for key in ("arguments", "input", "parameters", "body"):
            value = event.get(key)
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (ValueError, TypeError):
                    pass
        return event
    return {}


def handler(event: Any, context: Any) -> Any:
    logger.info("gateway tool invocation: event=%s client_context=%s",
                json.dumps(event, default=str)[:2000],
                json.dumps(getattr(getattr(context, "client_context", None), "custom", {}), default=str))

    tool = _tool_name(event if isinstance(event, dict) else {}, context)
    args = _arguments(event if isinstance(event, dict) else {})
    city = args.get("city", "Paris")
    datetime_iso = args.get("datetime_iso") or args.get("datetime")

    # Match on suffix: the gateway namespaces tools as "<target>___<tool>".
    if tool.endswith("get_weather"):
        return _provider.get_weather(city=city, datetime_iso=datetime_iso)
    if tool.endswith("get_events"):
        return _provider.get_events(city=city, datetime_iso=datetime_iso, event_types=_EVENT_TYPES)
    if tool.endswith("get_mobility"):
        return _provider.get_mobility(city=city, datetime_iso=datetime_iso)

    raise ValueError(f"Unknown gateway tool '{tool}'. event keys={list(args)}")
