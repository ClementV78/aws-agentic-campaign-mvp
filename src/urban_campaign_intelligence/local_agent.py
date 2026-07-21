from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from urban_campaign_intelligence.app_service import LIVE_CITY, UrbanCampaignApplicationService


RequestMode = Literal["scenario", "live"]


@dataclass(frozen=True)
class CampaignRequest:
    mode: RequestMode
    scenario_id: str | None = None
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
        if payload.get("scenario_id"):
            return CampaignRequest(mode="scenario", scenario_id=payload["scenario_id"])
        if not payload.get("datetime"):
            raise ValueError("Request payload requires either scenario_id or datetime.")
        return CampaignRequest(
            mode="live",
            datetime=payload["datetime"],
            city=payload.get("city", LIVE_CITY),
        )


class UrbanCampaignStrandsAgent:
    def __init__(self, app_service: UrbanCampaignApplicationService | None = None) -> None:
        self.app_service = app_service or UrbanCampaignApplicationService()

    def handle_request(self, request: CampaignRequest) -> dict[str, Any]:
        if request.mode == "scenario":
            if not request.scenario_id:
                raise ValueError("Scenario mode requires scenario_id.")
            return self.app_service.run_scenario_request(request.scenario_id)

        if not request.datetime:
            raise ValueError("Live mode requires datetime.")
        return self.app_service.run_live_request(datetime_str=request.datetime, city=request.city)
