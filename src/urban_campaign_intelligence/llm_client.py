"""Model access layer.

Strands is the default path: BedrockModel carries the Converse transport and
Agent.structured_output enforces the Pydantic contracts of llm_schemas. Custom code is
kept only where the SDK has nothing to offer — the fallback cascade below, which is an
architecture decision (ADR-007), not a gap in the SDK.

The deterministic core of the application never goes through this module: that exclusion
is deliberate (ADR-002), not a limitation.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

BEDROCK_REGION_ENV = "AWS_REGION"
BEDROCK_MODEL_ENV = "AGENTCAMPAIGN_BEDROCK_MODEL_ID"
BEDROCK_GUARDRAIL_ENV = "AGENTCAMPAIGN_BEDROCK_GUARDRAIL_ID"
BEDROCK_GUARDRAIL_VERSION_ENV = "AGENTCAMPAIGN_BEDROCK_GUARDRAIL_VERSION"
LLM_PROVIDER_ENV = "AGENTCAMPAIGN_LLM_PROVIDER"

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    """Interface shared by every provider, so call sites stay provider-agnostic."""

    provider: str
    model: str | None

    def is_configured(self) -> bool: ...

    def with_model(self, model: str | None) -> "LLMClient": ...

    def create_structured_output(self, system_prompt: str, user_prompt: str, output_model: type[T]) -> T: ...


class StrandsBedrockClient:
    """Amazon Bedrock through the Strands SDK.

    Credentials come from the default AWS chain, so the same code runs locally with a
    profile and inside AgentCore Runtime with the runtime role. Guardrails attach here
    when configured, which is where the DAT expects the generic controls to sit.
    """

    provider = "bedrock"
    last_usage: dict[str, Any] | None = None

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
        self._agent: Any | None = None

    def is_configured(self) -> bool:
        if not self.model or not self.region_name:
            return False
        try:
            import strands  # noqa: F401
        except ImportError:
            return False
        return True

    def with_model(self, model: str | None) -> "StrandsBedrockClient":
        return StrandsBedrockClient(
            model=model,
            region_name=self.region_name,
            timeout_seconds=self.timeout_seconds,
            max_attempts=self.max_attempts,
        )

    def _build_agent(self, system_prompt: str) -> Any:
        from botocore.config import Config
        from strands import Agent
        from strands.models import BedrockModel

        model_config: dict[str, Any] = {"model_id": self.model}
        guardrail_id = os.getenv(BEDROCK_GUARDRAIL_ENV)
        if guardrail_id:
            model_config["guardrail_id"] = guardrail_id
            model_config["guardrail_version"] = os.getenv(BEDROCK_GUARDRAIL_VERSION_ENV, "DRAFT")

        bedrock_model = BedrockModel(
            region_name=self.region_name,
            boto_client_config=Config(
                retries={"max_attempts": self.max_attempts, "mode": "adaptive"},
                read_timeout=self.timeout_seconds,
                connect_timeout=5,
            ),
            **model_config,
        )
        return Agent(model=bedrock_model, system_prompt=system_prompt)

    def create_structured_output(self, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
        if not self.is_configured():
            raise ValueError("Bedrock client is not configured.")
        try:
            agent = self._build_agent(system_prompt)
            result = agent.structured_output(output_model, user_prompt)
            # Strands accumulates token usage on the agent's event loop metrics.
            metrics = getattr(agent, "event_loop_metrics", None)
            self.last_usage = getattr(metrics, "accumulated_usage", None)
            return result
        except ValidationError as exc:
            raise ValueError(f"Bedrock returned output violating {output_model.__name__}: {exc}") from exc
        except Exception as exc:  # boto and strands raise many provider-specific errors
            raise ValueError(f"Bedrock request failed: {exc}") from exc


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

    def create_structured_output(self, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
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
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_payload = json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ValueError(f"OpenRouter request failed: {exc}") from exc

        try:
            content = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ValueError("OpenRouter returned an unexpected response shape.") from exc

        # Validated against the same contract as the Strands path.
        try:
            return output_model.model_validate_json(content)
        except ValidationError as exc:
            raise ValueError(f"OpenRouter returned output violating {output_model.__name__}: {exc}") from exc


class NullLLMClient:
    """Returned when no provider is usable, so call sites degrade deterministically."""

    provider = "none"
    model: str | None = None

    def is_configured(self) -> bool:
        return False

    def with_model(self, model: str | None) -> "NullLLMClient":
        return self

    def create_structured_output(self, system_prompt: str, user_prompt: str, output_model: type[T]) -> T:
        raise ValueError("No LLM provider is configured.")


def get_llm_client() -> LLMClient:
    """Resolve the active provider: Bedrock via Strands, then OpenRouter, then deterministic.

    AGENTCAMPAIGN_LLM_PROVIDER forces one provider instead of walking the cascade.
    """
    forced = (os.getenv(LLM_PROVIDER_ENV) or "").strip().lower()
    bedrock = StrandsBedrockClient()
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
