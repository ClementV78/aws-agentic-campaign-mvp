from __future__ import annotations

from typing import Any


IMPACT_LEVEL_FACTORS = {"low": 0.45, "medium": 0.7, "high": 1.0}
TIME_SLOT_ALIGNMENT = {"morning": 0.9, "afternoon": 1.0, "evening": 1.0, "night": 0.75}


def _derive_urban_signals(
    time_context: dict[str, Any],
    weather: dict[str, Any],
    events: list[dict[str, Any]],
    mobility: dict[str, Any],
) -> dict[str, str]:
    premium_activity = "high" if any("premium_zone" in event.get("impact_tags", []) for event in events) else "low"
    tourist_density = "high" if "good_weather" in weather["impact_tags"] or premium_activity == "high" else "medium"
    commuter_density = "high" if mobility["global_status"] in {"station_peak", "normal"} and time_context["day_type"] == "weekday" else "medium"
    family_leisure = "high" if time_context["school_holiday"] or time_context["day_type"] == "weekend" else "medium"
    return {
        "tourist_density": tourist_density,
        "commuter_density": commuter_density,
        "premium_activity": premium_activity,
        "family_leisure": family_leisure,
    }


def _compute_event_influence_by_zone(
    time_context: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    influence_by_zone: dict[str, dict[str, Any]] = {}
    for event in events:
        intensity = float(event.get("intensity", 0.7))
        impact_factor = IMPACT_LEVEL_FACTORS.get(event.get("impact_level", "medium"), 0.7)
        active_time_slots = event.get("active_time_slots") or []
        time_alignment = TIME_SLOT_ALIGNMENT.get(time_context["time_slot"], 1.0)
        if active_time_slots and time_context["time_slot"] not in active_time_slots:
            time_alignment *= 0.55

        zone_weights = event.get("zone_weights") or {zone_id: 1.0 for zone_id in event.get("zone_ids", [])}
        for zone_id, zone_weight in zone_weights.items():
            score = round(min(1.0, float(zone_weight) * intensity * impact_factor * time_alignment), 4)
            zone_entry = influence_by_zone.setdefault(
                zone_id,
                {"score": 0.0, "event_count": 0, "top_event": None, "event_names": [], "impact_tags": []},
            )
            zone_entry["score"] = round(min(1.0, zone_entry["score"] + score), 4)
            zone_entry["event_count"] += 1
            zone_entry["event_names"].append(event.get("display_name", event.get("type", "unknown_event")))
            zone_entry["impact_tags"] = sorted(set(zone_entry["impact_tags"]) | set(event.get("impact_tags", [])))
            if zone_entry["top_event"] is None or score > zone_entry["top_event"]["score"]:
                zone_entry["top_event"] = {
                    "type": event.get("type"),
                    "display_name": event.get("display_name", event.get("type", "unknown_event")),
                    "score": score,
                }

    return influence_by_zone


def build_city_context(
    normalized_input: dict[str, Any],
    time_context: dict[str, Any],
    weather: dict[str, Any],
    events: list[dict[str, Any]],
    mobility: dict[str, Any],
    degraded_signals: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    warnings: list[str] = []
    if mobility["global_status"] == "major_disruption":
        warnings.append("Major mobility disruption may reduce recommendation confidence.")
    confidence = 0.86
    if warnings:
        confidence -= 0.12

    # Signals the caller could not resolve are surfaced rather than silently defaulted.
    for degraded_signal in degraded_signals or []:
        warnings.append(degraded_signal)
        confidence -= 0.04
    if time_context.get("school_holiday") is None:
        warnings.append("School calendar unknown for this request; family signals may be understated.")
        confidence -= 0.04
    if any(event["impact_level"] == "high" for event in events):
        confidence += 0.03
    event_influence_by_zone = _compute_event_influence_by_zone(time_context=time_context, events=events)

    city_context = {
        "city": normalized_input["city"],
        "datetime": normalized_input["datetime"],
        "time_context": time_context,
        "weather": weather,
        "events": events,
        "event_influence_by_zone": event_influence_by_zone,
        "mobility": mobility,
        "urban_signals": _derive_urban_signals(time_context, weather, events, mobility),
        "warnings": warnings,
        "confidence": max(0.0, min(1.0, round(confidence, 2))),
    }
    log_entry = {
        "step": "city_context_builder",
        "status": "completed",
        "details": {
            "event_count": len(events),
            "event_influenced_zone_count": len(event_influence_by_zone),
            "warning_count": len(warnings),
            "time_slot": time_context["time_slot"],
        },
    }
    return city_context, log_entry
