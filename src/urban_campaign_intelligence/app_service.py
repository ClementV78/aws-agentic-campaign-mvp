from __future__ import annotations

from datetime import datetime
from typing import Any

from urban_campaign_intelligence.city_context import build_city_context
from urban_campaign_intelligence.context_agents import (
    EVENT_MAPPINGS,
    run_events_agent,
    run_mobility_agent,
    run_weather_agent,
)
from urban_campaign_intelligence.data_access import (
    get_scenario_by_id,
    load_advertisers,
    load_weights,
    load_zones,
)
from urban_campaign_intelligence.executive_summary import generate_executive_summary
from urban_campaign_intelligence.gateway_tools import (
    EVENT_TOOL_RESPONSES,
    MOBILITY_TOOL_RESPONSES,
    WEATHER_TOOL_RESPONSES,
    GatewayProvider,
)
from urban_campaign_intelligence.pre_hook import run_pre_hook
from urban_campaign_intelligence.review import review_allocation
from urban_campaign_intelligence.scoring import allocate_campaigns, score_allocations


LIVE_CITY = "Paris"
LIVE_REQUEST_ID = "live_request"
LIVE_REQUEST_NAME = "Live Paris Request"


class UrbanCampaignApplicationService:
    def __init__(self, live_city: str = LIVE_CITY) -> None:
        self.live_city = live_city

    def run_scenario_request(self, scenario_id: str) -> dict[str, Any]:
        scenario = get_scenario_by_id(scenario_id)
        scenario_inputs = self._get_scenario_inputs(scenario)
        weather_payload = self._build_scenario_weather_payload(
            city=scenario["city"],
            datetime_iso=scenario["datetime"],
            weather_input=scenario_inputs.get("weather"),
        )
        events_payload = self._build_scenario_events_payload(
            city=scenario["city"],
            datetime_iso=scenario["datetime"],
            event_inputs=scenario_inputs.get("events", []),
        )
        mobility_payload = self._build_scenario_mobility_payload(
            city=scenario["city"],
            datetime_iso=scenario["datetime"],
            mobility_input=scenario_inputs.get("mobility"),
        )
        return self._run_pipeline(
            scenario=scenario,
            weather_payload=weather_payload,
            events_payload=events_payload,
            mobility_payload=mobility_payload,
            request_mode="scenario",
        )

    def run_live_request(self, datetime_str: str, city: str = LIVE_CITY) -> dict[str, Any]:
        if city.strip().lower() != self.live_city.lower():
            raise ValueError(f"Live mode currently supports {self.live_city} only.")

        scenario = self._build_live_scenario(datetime_str=datetime_str, city=self.live_city)
        gateway_provider = GatewayProvider()
        weather_payload = gateway_provider.get_weather(city=self.live_city, datetime_iso=scenario["datetime"])
        events_payload = gateway_provider.get_events(
            city=self.live_city,
            datetime_iso=scenario["datetime"],
            event_types=list(EVENT_MAPPINGS.keys()),
        )
        mobility_payload = gateway_provider.get_mobility(city=self.live_city, datetime_iso=scenario["datetime"])

        degraded_signals: list[str] = []
        events_payload, events_warning = self._reject_synthetic_live_events(events_payload)
        if events_warning:
            degraded_signals.append(events_warning)

        return self._run_pipeline(
            scenario=scenario,
            weather_payload=weather_payload,
            events_payload=events_payload,
            mobility_payload=mobility_payload,
            request_mode="live",
            degraded_signals=degraded_signals,
        )

    @staticmethod
    def _reject_synthetic_live_events(events_payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        """Live mode must not present the canned event catalogue as real context.

        The mock provider answers a list of event types with one canned event per type, which
        would make every live request claim that a concert, a fashion show, a match and a family
        festival happen at once. When no real source answered, degrade to no events and say so.
        """
        if events_payload.get("provider_mode") not in {"mock", "mock_fallback"}:
            return events_payload, None
        degraded = {**events_payload, "events": [], "degraded": True}
        return degraded, "No real event source answered; live request ran without event context."

    @staticmethod
    def _get_scenario_inputs(scenario: dict[str, Any]) -> dict[str, Any]:
        if "inputs" in scenario:
            return scenario["inputs"]
        signals = scenario.get("signals", {})
        return {
            "weather": {"mode": "mock", "raw_condition": signals.get("weather", "clear")},
            "events": [{"mode": "mock", "event_type": event_type} for event_type in signals.get("events", [])],
            "mobility": {"mode": "mock", "network_status": signals.get("mobility", "normal")},
        }

    @staticmethod
    def _build_scenario_weather_payload(city: str, datetime_iso: str, weather_input: dict[str, Any] | None) -> dict[str, Any]:
        if weather_input:
            response = {
                "provider": "mock_scenarios",
                "provider_mode": "scenario_injected",
                "raw_condition": weather_input.get("raw_condition", "clear"),
                "temperature_c": weather_input.get("temperature_c", 20),
                "precipitation_mm": weather_input.get("precipitation_mm", 0.0),
                "wind_kph": weather_input.get("wind_kph", 10),
            }
        else:
            raw_condition = "clear"
            response = {
                "provider": "mock_scenarios",
                "provider_mode": "scenario_injected",
                **WEATHER_TOOL_RESPONSES.get(raw_condition, WEATHER_TOOL_RESPONSES["clear"]),
            }
        return {"city": city, "datetime": datetime_iso, **response}

    @staticmethod
    def _build_scenario_events_payload(city: str, datetime_iso: str, event_inputs: list[dict[str, Any]] | None) -> dict[str, Any]:
        events = []
        for raw_event in event_inputs or []:
            event_type = raw_event.get("event_type", "generic_event")
            event = {
                **EVENT_TOOL_RESPONSES.get(
                    event_type,
                    {
                        "provider": "mock_scenarios",
                        "event_type": event_type,
                        "display_name": raw_event.get("title", event_type.replace("_", " ").title()),
                        "zone_ids": [],
                        "impact_level": "medium",
                        "start_local": None,
                    },
                ),
                **raw_event,
                "provider": "mock_scenarios",
                "display_name": raw_event.get("title") or raw_event.get("display_name") or event_type.replace("_", " ").title(),
            }
            events.append(event)
        return {"city": city, "datetime": datetime_iso, "events": events, "provider_mode": "scenario_injected"}

    @staticmethod
    def _build_scenario_mobility_payload(city: str, datetime_iso: str, mobility_input: dict[str, Any] | None) -> dict[str, Any]:
        if mobility_input:
            response = {
                "provider": "mock_scenarios",
                "provider_mode": "scenario_injected",
                "network_status": mobility_input.get("network_status", "normal"),
                "severity": mobility_input.get("severity", "low"),
                "affected_zone_ids": mobility_input.get("affected_zone_ids", []),
                **({"prediction_confidence": mobility_input["prediction_confidence"]} if "prediction_confidence" in mobility_input else {}),
                **({"prediction_basis": mobility_input["prediction_basis"]} if "prediction_basis" in mobility_input else {}),
            }
        else:
            response = {
                "provider": "mock_scenarios",
                "provider_mode": "scenario_injected",
                **MOBILITY_TOOL_RESPONSES["normal"],
            }
        return {"city": city, "datetime": datetime_iso, **response}

    @staticmethod
    def _build_live_scenario(datetime_str: str, city: str = LIVE_CITY) -> dict[str, Any]:
        dt = datetime.fromisoformat(datetime_str)
        return {
            "id": LIVE_REQUEST_ID,
            "name": LIVE_REQUEST_NAME,
            "city": city,
            "datetime": dt.isoformat(),
            "calendar": {
                "day_type": "weekend" if dt.weekday() >= 5 else "weekday",
                # No school calendar source is wired yet: stay unknown rather than assert False,
                # which would silently understate family signals during school holidays.
                "school_holiday": None,
            },
            "inputs": {},
        }

    @staticmethod
    def _build_tool_log_entries(
        weather_payload: dict[str, Any],
        events_payload: dict[str, Any],
        mobility_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "tool": "get_weather",
                "status": "completed",
                "details": {
                    "provider": weather_payload["provider"],
                    "provider_mode": weather_payload.get("provider_mode", "unknown"),
                    "fallback": weather_payload.get("provider_fallback"),
                    "raw_condition": weather_payload["raw_condition"],
                },
            },
            {
                "tool": "get_events",
                "status": "completed",
                "details": {
                    "provider": events_payload["events"][0]["provider"] if events_payload["events"] else "none",
                    "provider_mode": events_payload.get("provider_mode", "unknown"),
                    "fallback": events_payload.get("provider_fallback"),
                    "event_count": len(events_payload["events"]),
                },
            },
            {
                "tool": "get_mobility",
                "status": "completed",
                "details": {
                    "provider": mobility_payload["provider"],
                    "provider_mode": mobility_payload.get("provider_mode", "unknown"),
                    "fallback": mobility_payload.get("provider_fallback"),
                    "network_status": mobility_payload["network_status"],
                },
            },
        ]

    def _run_pipeline(
        self,
        scenario: dict[str, Any],
        weather_payload: dict[str, Any],
        events_payload: dict[str, Any],
        mobility_payload: dict[str, Any],
        request_mode: str,
        degraded_signals: list[str] | None = None,
    ) -> dict[str, Any]:
        zones = load_zones()
        advertisers = load_advertisers()
        weights = load_weights()

        execution_log: list[dict[str, Any]] = []

        pre_hook_output, pre_hook_log = run_pre_hook(scenario)
        execution_log.extend(pre_hook_log)
        execution_log.extend(self._build_tool_log_entries(weather_payload, events_payload, mobility_payload))

        weather_log, weather = run_weather_agent(weather_payload)
        events_log, events = run_events_agent(events_payload)
        mobility_log, mobility = run_mobility_agent(mobility_payload)
        execution_log.extend([weather_log, events_log, mobility_log])

        city_context, context_log = build_city_context(
            normalized_input=pre_hook_output["input"],
            time_context=pre_hook_output["time_context"],
            weather=weather,
            events=events,
            mobility=mobility,
            degraded_signals=degraded_signals,
        )
        execution_log.append(context_log)

        scorecards, scoring_logs = score_allocations(zones, advertisers, city_context, weights)
        execution_log.extend(scoring_logs)

        allocation_plan, allocation_log = allocate_campaigns(scorecards)
        execution_log.append(allocation_log)

        review, review_log = review_allocation(city_context, allocation_plan)
        execution_log.append(review_log)
        executive_summary, executive_summary_log = generate_executive_summary(
            scenario=scenario,
            city_context=city_context,
            allocation_plan=allocation_plan,
            review=review,
        )
        execution_log.append(executive_summary_log)

        return {
            "scenario": {
                "id": scenario["id"],
                "name": scenario["name"],
                "city": scenario["city"],
                "datetime": scenario["datetime"],
                "mode": request_mode,
            },
            "city_context": city_context,
            "allocation_plan": allocation_plan,
            "review": review,
            "executive_summary": executive_summary,
            "execution_log": execution_log,
        }


DEFAULT_APP_SERVICE = UrbanCampaignApplicationService()


def run_scenario_request(scenario_id: str) -> dict[str, Any]:
    return DEFAULT_APP_SERVICE.run_scenario_request(scenario_id)


def run_live_request(datetime_str: str, city: str = LIVE_CITY) -> dict[str, Any]:
    return DEFAULT_APP_SERVICE.run_live_request(datetime_str=datetime_str, city=city)
