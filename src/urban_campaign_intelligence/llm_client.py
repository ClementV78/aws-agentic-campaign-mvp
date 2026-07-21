from __future__ import annotations

import json
import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

BEDROCK_REGION_ENV = "AWS_REGION"
BEDROCK_MODEL_ENV = "AGENTCAMPAIGN_BEDROCK_MODEL_ID"
LLM_PROVIDER_ENV = "AGENTCAMPAIGN_LLM_PROVIDER"

# Bedrock has no response_format flag: a tool schema is the supported way to force
# structured output through the Converse API.
_JSON_TOOL_NAME = "emit_json"
_JSON_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": _JSON_TOOL_NAME,
                "description": "Return the answer as a single JSON object.",
                "inputSchema": {"json": {"type": "object", "properties": {}, "additionalProperties": True}},
            }
        }
    ],
    "toolChoice": {"tool": {"name": _JSON_TOOL_NAME}},
}


class LLMClient(Protocol):
    """Interface shared by every provider, so call sites stay provider-agnostic."""

    model: str | None

    def is_configured(self) -> bool: ...

    def with_model(self, model: str | None) -> "LLMClient": ...

    def create_json_completion(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class BedrockClient:
    """Amazon Bedrock client using the Converse API.

    Credentials come from the default AWS chain, so the same code runs locally with a
    profile and inside AgentCore Runtime with the runtime role.
    """

    provider = "bedrock"

    def __init__(
        self,
        model: str | None = None,
        region_name: str | None = None,
        timeout_seconds: int = 20,
        max_attempts: int = 3,
    ) -> None:
        self.model = model or os.getenv(BEDROCK_MODEL_ENV)
        self.region_name = region_name or os.getenv(BEDROCK_REGION_ENV) or os.getenv("AWS_DEFAULT_REGION")
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self._runtime: Any | None = None

    def is_configured(self) -> bool:
        if not self.model or not self.region_name:
            return False
        try:
            import boto3  # noqa: F401
        except ImportError:
            return False
        return True

    def with_model(self, model: str | None) -> "BedrockClient":
        return BedrockClient(
            model=model,
            region_name=self.region_name,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
        )

    def _get_runtime(self) -> Any:
        # boto3 client construction resolves credentials and endpoints: build it once.
        if self._runtime is None:
            import boto3
            from botocore.config import Config

            self._runtime = boto3.client(
                "bedrock-runtime",
                region_name=self.region_name,
                config=Config(
                    retries={"max_attempts": self.max_attempts, "mode": "adaptive"},
                    read_timeout=self.timeout_seconds,
                    connect_timeout=5,
                ),
            )
        return self._runtime

    def create_json_completion(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError("Bedrock client is not configured.")

        try:
            response = self._get_runtime().converse(
                modelId=self.model,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                toolConfig=_JSON_TOOL_CONFIG,
            )
        except Exception as exc:  # botocore raises many client-specific errors
            raise ValueError(f"Bedrock request failed: {exc}") from exc

        self.last_usage = response.get("usage")
        for block in response.get("output", {}).get("message", {}).get("content", []):
            tool_use = block.get("toolUse")
            if tool_use and isinstance(tool_use.get("input"), dict):
                return tool_use["input"]
        raise ValueError("Bedrock returned no structured tool output.")


class OpenRouterClient:
    """Transitional provider for local iteration. Slated for removal, see ADR-007."""

    provider = "openrouter"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_seconds: int = 20) -> None:
        self.api_key = api_key or os.getenv("AGENTCAMPAIGN_OPENROUTER_API_KEY")
        self.model = model or os.getenv("AGENTCAMPAIGN_OPENROUTER_MODEL")
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def with_model(self, model: str | None) -> "OpenRouterClient":
        return OpenRouterClient(api_key=self.api_key, model=model, timeout_seconds=self.timeout_seconds)

    def create_json_completion(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError("OpenRouter client is not configured.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        request = Request(
            OPENROUTER_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_payload = json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ValueError(f"OpenRouter request failed: {exc}") from exc

        try:
            content = response_payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ValueError("OpenRouter returned an invalid JSON completion.") from exc


class NullLLMClient:
    """Returned when no provider is usable, so call sites degrade deterministically."""

    provider = "none"
    model: str | None = None

    def is_configured(self) -> bool:
        return False

    def with_model(self, model: str | None) -> "NullLLMClient":
        return self

    def create_json_completion(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raise ValueError("No LLM provider is configured.")


def get_llm_client() -> LLMClient:
    """Resolve the active provider: Bedrock, then OpenRouter, then deterministic.

    AGENTCAMPAIGN_LLM_PROVIDER forces one provider instead of walking the cascade.
    """
    forced = (os.getenv(LLM_PROVIDER_ENV) or "").strip().lower()
    bedrock = BedrockClient()
    openrouter = OpenRouterClient()

    if forced == "bedrock":
        return bedrock
    if forced == "openrouter":
        return openrouter

    if bedrock.is_configured():
        return bedrock
    if openrouter.is_configured():
        return openrouter
    return NullLLMClient()
