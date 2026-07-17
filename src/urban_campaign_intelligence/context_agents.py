from __future__ import annotations

import os
from typing import Any

from urban_campaign_intelligence.llm_client import OpenRouterClient


EVENT_MAPPINGS: dict[str, dict[str, Any]] = {
    "major_concert": {
        "zone_ids": ["accor_arena", "gare_de_lyon", "bercy_village"],
        "zone_weights": {"accor_arena": 1.0, "gare_de_lyon": 0.75, "bercy_village": 0.55},
        "impact_level": "high",
        "impact_tags": ["events", "high_footfall", "young_audience"],
        "audience_tags": ["concert_goers", "young_adults"],
        "active_time_slots": ["evening"],
        "intensity": 0.95,
    },
    "fashion_event": {
        "zone_ids": ["avenue_montaigne", "saint_germain_des_pres", "champs_elysees", "opera"],
        "zone_weights": {
            "avenue_montaigne": 1.0,
            "saint_germain_des_pres": 0.85,
            "champs_elysees": 0.8,
            "opera": 0.65,
        },
        "impact_level": "high",
        "impact_tags": ["fashion_event", "premium_zone", "tourist_density"],
        "audience_tags": ["luxury_shoppers", "high_income_visitors", "tourists"],
        "active_time_slots": ["afternoon", "evening"],
        "intensity": 0.92,
    },
    "sports_event": {
        "zone_ids": ["parc_des_princes", "stade_de_france", "chatelet"],
        "zone_weights": {"parc_des_princes": 1.0, "stade_de_france": 0.9, "chatelet": 0.35},
        "impact_level": "high",
        "impact_tags": ["sports_event", "high_footfall", "sports_fans"],
        "audience_tags": ["sports_fans", "young_adults"],
        "active_time_slots": ["afternoon", "evening"],
        "intensity": 0.9,
    },
    "family_event": {
        "zone_ids": ["vincennes", "la_villette", "gare_de_lyon"],
        "zone_weights": {"vincennes": 1.0, "la_villette": 0.8, "gare_de_lyon": 0.45},
        "impact_level": "medium",
        "impact_tags": ["family_leisure", "weekend_visitors", "events"],
        "audience_tags": ["families", "weekend_visitors"],
        "active_time_slots": ["morning", "afternoon"],
        "intensity": 0.7,
    },
}

MOBILITY_MAPPINGS: dict[str, dict[str, Any]] = {
    "normal": {"global_status": "normal", "affected_zone_ids": [], "impact_tags": ["high_mobility"]},
    "localized_peak": {
        "global_status": "localized_peak",
        "affected_zone_ids": ["accor_arena", "gare_de_lyon", "bercy_village"],
        "impact_tags": ["events", "high_mobility"],
    },
    "major_transport_disruption": {
        "global_status": "major_disruption",
        "affected_zone_ids": ["gare_du_nord", "gare_de_lyon", "gare_montparnasse", "gare_saint_lazare", "chatelet", "republique"],
        "impact_tags": ["major_transport_disruption", "low_mobility", "risk_context"],
    },
    "dense_central": {
        "global_status": "dense_central",
        "affected_zone_ids": ["opera", "champs_elysees", "boulevard_haussmann", "avenue_montaigne"],
        "impact_tags": ["premium_zone", "tourist_density", "high_mobility"],
    },
    "station_peak": {
        "global_status": "station_peak",
        "affected_zone_ids": ["gare_du_nord", "gare_de_lyon", "gare_montparnasse", "gare_saint_lazare"],
        "impact_tags": ["station_area", "holiday_departure", "high_mobility"],
    },
}
def run_weather_agent(weather_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_condition = weather_payload["raw_condition"]
    impact_tags: list[str] = []
    if weather_payload["temperature_c"] >= 30:
        impact_tags.extend(["hot_weather", "high_footfall", "cold_drink_relevance"])
        summary = "hot"
    elif weather_payload["temperature_c"] <= 7:
        impact_tags.extend(["cold_weather", "indoor_bias"])
        summary = "cold"
    elif weather_payload["precipitation_mm"] > 1.0:
        impact_tags.extend(["rainy_weather", "indoor_bias"])
        summary = "rain"
    elif raw_condition == "clear":
        impact_tags.extend(["good_weather", "outdoor_activity"])
        summary = "clear"
    else:
        impact_tags.append("neutral_weather")
        summary = raw_condition

    weather = {
        "summary": summary,
        "temperature_c": weather_payload["temperature_c"],
        "impact_tags": impact_tags,
        "source": weather_payload["provider"],
    }
    return (
        {
            "agent": "weather_agent",
            "status": "completed",
            "details": {
                "raw_condition": raw_condition,
                "temperature_c": weather_payload["temperature_c"],
                "impact_tags": weather["impact_tags"],
            },
        },
        weather,
    )


def run_events_agent(events_payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    llm_mode = os.getenv("EVENTS_AGENT_MODE", "heuristic").strip().lower()
    if llm_mode == "llm":
        llm_result = _run_events_agent_llm(events_payload)
        if llm_result is not None:
            return llm_result

    events = []
    for raw_event in events_payload.get("events", []):
        event_type = raw_event["event_type"]
        mapping = EVENT_MAPPINGS.get(
            event_type,
            {"zone_ids": [], "impact_level": "medium", "impact_tags": ["events"]},
        )
        events.append(
            {
                "type": event_type,
                "display_name": raw_event["display_name"],
                "title": raw_event.get("title", raw_event["display_name"]),
                "venue": raw_event.get("venue"),
                "description": raw_event.get("description"),
                "audience_hint": raw_event.get("audience_hint", []),
                "raw_tags": raw_event.get("raw_tags", []),
                "source": raw_event["provider"],
                "source_url": raw_event.get("source_url"),
                "address_name": raw_event.get("address_name"),
                "address_city": raw_event.get("address_city"),
                "start_local": raw_event.get("start_local"),
                **mapping,
            }
        )
    return (
        {"agent": "events_agent", "status": "completed", "details": {"event_count": len(events), "event_types": [event["type"] for event in events]}},
        events,
    )


def _run_events_agent_llm(events_payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    client = OpenRouterClient()
    if not client.is_configured():
        return None

    events = []
    fallback_count = 0
    for raw_event in events_payload.get("events", []):
        try:
            llm_event = _classify_event_with_llm(client, raw_event)
            events.append(llm_event)
        except ValueError:
            fallback_count += 1
            mapping = EVENT_MAPPINGS.get(
                raw_event["event_type"],
                {"zone_ids": [], "impact_level": "medium", "impact_tags": ["events"]},
            )
            events.append(
                {
                    "type": raw_event["event_type"],
                    "display_name": raw_event["display_name"],
                    "title": raw_event.get("title", raw_event["display_name"]),
                    "venue": raw_event.get("venue"),
                    "description": raw_event.get("description"),
                    "audience_hint": raw_event.get("audience_hint", []),
                    "raw_tags": raw_event.get("raw_tags", []),
                    "source": raw_event["provider"],
                    "source_url": raw_event.get("source_url"),
                    "address_name": raw_event.get("address_name"),
                    "address_city": raw_event.get("address_city"),
                    "start_local": raw_event.get("start_local"),
                    **mapping,
                }
            )

    return (
        {
            "agent": "events_agent",
            "status": "completed",
            "details": {
                "event_count": len(events),
                "event_types": [event["type"] for event in events],
                "mode": "llm",
                "fallback_count": fallback_count,
            },
        },
        events,
    )


def _classify_event_with_llm(client: OpenRouterClient, raw_event: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "You are an event classification component for an urban campaign allocation system. "
        "Return strict JSON only. "
        "You classify a Paris event into a small business taxonomy and estimate likely impact."
    )
    user_prompt = json_prompt_for_event(raw_event)
    payload = client.create_json_completion(system_prompt=system_prompt, user_prompt=user_prompt)

    event_type = payload.get("event_type", raw_event["event_type"])
    impact_level = payload.get("impact_level", "medium")
    impact_tags = payload.get("impact_tags", ["events"])
    zone_ids = payload.get("zone_ids") or EVENT_MAPPINGS.get(event_type, {}).get("zone_ids", [])
    if not isinstance(impact_tags, list) or not isinstance(zone_ids, list):
        raise ValueError("LLM event classification payload is invalid.")

    return {
        "type": event_type,
        "display_name": raw_event["display_name"],
        "title": raw_event.get("title", raw_event["display_name"]),
        "venue": raw_event.get("venue"),
        "description": raw_event.get("description"),
        "audience_hint": raw_event.get("audience_hint", []),
        "raw_tags": raw_event.get("raw_tags", []),
        "source": raw_event["provider"],
        "source_url": raw_event.get("source_url"),
        "address_name": raw_event.get("address_name"),
        "address_city": raw_event.get("address_city"),
        "start_local": raw_event.get("start_local"),
        "zone_ids": zone_ids,
        "impact_level": impact_level,
        "impact_tags": impact_tags,
        "zone_weights": payload.get("zone_weights") or {
            zone_id: 1.0 for zone_id in zone_ids
        },
        "audience_tags": payload.get("audience_tags", []),
        "active_time_slots": payload.get("active_time_slots", []),
        "intensity": payload.get("intensity", 0.7),
    }


def json_prompt_for_event(raw_event: dict[str, Any]) -> str:
    return (
        "Classify this event and return JSON with keys: "
        'event_type, impact_level, impact_tags, zone_ids, zone_weights, audience_tags, active_time_slots, intensity. '
        "Allowed event_type values: major_concert, fashion_event, sports_event, family_event, cultural_event, generic_event. "
        "Allowed impact_level values: low, medium, high. "
        "impact_tags must be a JSON array of short snake_case strings. "
        "zone_ids must be a JSON array of likely impacted internal zone ids. "
        "zone_weights must be a JSON object mapping zone ids to influence weights between 0 and 1. "
        "audience_tags must be a JSON array of audience tags. "
        "active_time_slots must be a JSON array using morning, afternoon, evening, night. "
        "intensity must be a float between 0 and 1. "
        f"Event data: {raw_event}"
    )


def run_mobility_agent(mobility_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    mobility_key = mobility_payload["network_status"]
    mobility = dict(
        MOBILITY_MAPPINGS.get(
        mobility_key,
        {"global_status": mobility_key, "affected_zone_ids": [], "impact_tags": []},
    )
    )
    if mobility_payload.get("affected_zone_ids"):
        mobility["affected_zone_ids"] = mobility_payload["affected_zone_ids"]
    mobility["source"] = mobility_payload["provider"]
    return (
        {
            "agent": "mobility_agent",
            "status": "completed",
            "details": {
                "mobility_key": mobility_key,
                "severity": mobility_payload["severity"],
                "affected_zone_count": len(mobility["affected_zone_ids"]),
            },
        },
        mobility,
    )
