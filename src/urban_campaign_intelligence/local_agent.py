from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from urban_campaign_intelligence.app_service import LIVE_CITY, UrbanCampaignApplicationService


RequestMode = Literal["prompt", "scenario", "live"]

# Inline scenario injects the scoring context through the payload. It is a test capability,
# not a product feature, so it is off by default (secure-by-default): the deployed prod endpoint
# never enables it, a test/dev endpoint or the CI pipeline sets the flag. This flag governs the
# structured-signal surface, which guardrails cannot see (it is data, not a prompt); the free-text
# that reaches the LLM stays covered by guardrails independently. See ARCHITECTURE.md §8.2.
INLINE_SCENARIO_FLAG = "AGENTCAMPAIGN_ALLOW_INLINE_SCENARIO"


def _inline_scenario_allowed() -> bool:
    return os.getenv(INLINE_SCENARIO_FLAG, "").strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class CampaignRequest:
    mode: RequestMode
    prompt: str | None = None
    scenario_id: str | None = None
    # Inline scenario carried by the payload: deployable and reads no file, so it smoke-tests the
    # deployed runtime deterministically without the external tools. scenario_id stays a local-only
    # shortcut into the dev catalogue (data/scenarios.json).
    scenario: dict[str, Any] | None = None
    datetime: str | None = None
    city: str = LIVE_CITY


class LocalRequestMapper:
    @staticmethod
    def from_cli_args(args: Any) -> CampaignRequest:
        if getattr(args, "scenario", None):
            return CampaignRequest(mode="scenario", scenario_id=args.scenario)
        return CampaignRequest(mode="live", datetime=args.datetime, city=getattr(args, "city", LIVE_CITY))

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> CampaignRequest:
        if payload.get("prompt"):
            return CampaignRequest(mode="prompt", prompt=payload["prompt"])
        if isinstance(payload.get("scenario"), dict):
            if not _inline_scenario_allowed():
                raise ValueError(
                    "Inline scenario is disabled. Set AGENTCAMPAIGN_ALLOW_INLINE_SCENARIO=1 to "
                    "enable it (test/dev only; keep it off in production)."
                )
            return CampaignRequest(mode="scenario", scenario=payload["scenario"])
        if payload.get("scenario_id"):
            return CampaignRequest(mode="scenario", scenario_id=payload["scenario_id"])
        if not payload.get("datetime"):
            raise ValueError("Request payload requires a scenario, a scenario_id, or a datetime.")
        return CampaignRequest(
            mode="live",
            datetime=payload["datetime"],
            city=payload.get("city", LIVE_CITY),
        )


class UrbanCampaignStrandsAgent:
    def __init__(self, app_service: UrbanCampaignApplicationService | None = None) -> None:
        self.app_service = app_service or UrbanCampaignApplicationService()

    def handle_request(self, request: CampaignRequest) -> dict[str, Any]:
        if request.mode == "prompt":
            if not request.prompt:
                raise ValueError("Prompt mode requires a prompt.")
            return self.app_service.run_prompt_request(request.prompt)

        if request.mode == "scenario":
            if request.scenario is not None:
                return self.app_service.run_scenario_request(scenario=request.scenario)
            if not request.scenario_id:
                raise ValueError("Scenario mode requires a scenario or a scenario_id.")
            return self.app_service.run_scenario_request(scenario_id=request.scenario_id)

        if not request.datetime:
            raise ValueError("Live mode requires datetime.")
        return self.app_service.run_live_request(datetime_str=request.datetime, city=request.city)
