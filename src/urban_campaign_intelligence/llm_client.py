from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient:
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
