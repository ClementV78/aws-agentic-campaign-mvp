from __future__ import annotations

from typing import Any


TRAFFIC_SCORES = {"low": 0.25, "medium": 0.5, "high": 0.75, "very_high": 0.95}
WEATHER_SENSITIVITY = {"low": 0.9, "medium": 0.7, "high": 0.45}
RECOMMENDED_MATCH_COUNT = 10
MAX_RECOMMENDED_PER_ADVERTISER = 2
# Single-brand mode: the focused advertiser may take a majority of the billboards, but not all —
# the rest stay open to the other brands, so the plan stays proportional rather than exclusive.
MAX_RECOMMENDED_FOR_FOCUS = 6


def _score_zone_attractiveness(zone: dict[str, Any], city_context: dict[str, Any]) -> tuple[float, list[str]]:
    reasons = []
    traffic_score = TRAFFIC_SCORES[zone["traffic_level"]]
    time_audience = set(zone["audience_by_time"].get(city_context["time_context"]["time_slot"], []))
    weather_score = WEATHER_SENSITIVITY[zone["weather_sensitivity"]]
    if "good_weather" in city_context["weather"]["impact_tags"]:
        weather_score = min(1.0, weather_score + 0.15)
    elif "hot_weather" in city_context["weather"]["impact_tags"] and zone["weather_sensitivity"] != "low":
        weather_score = min(1.0, weather_score + 0.2)
    elif "cold_weather" in city_context["weather"]["impact_tags"]:
        weather_score = max(0.2, weather_score - 0.2)

    event_influence = city_context.get("event_influence_by_zone", {}).get(zone["id"], {})
    event_bonus = min(0.3, event_influence.get("score", 0.0) * 0.3)
    mobility_bonus = 0.15 if zone["id"] in city_context["mobility"]["affected_zone_ids"] and city_context["mobility"]["global_status"] != "major_disruption" else 0.0
    mobility_penalty = 0.25 if zone["id"] in city_context["mobility"]["affected_zone_ids"] and city_context["mobility"]["global_status"] == "major_disruption" else 0.0

    if event_bonus:
        top_event = event_influence.get("top_event", {})
        reasons.append(
            f"zone boosted by local event activity ({top_event.get('display_name', 'event context')})"
        )
    if mobility_bonus:
        reasons.append("zone benefits from localized mobility peak")
    if mobility_penalty:
        reasons.append("zone penalized by transport disruption")
    if time_audience:
        reasons.append(f"time-slot audience active: {', '.join(sorted(time_audience))}")

    score = (
        traffic_score * 0.35
        + zone["premium_index"] * 0.25
        + weather_score * 0.2
        + event_bonus
        + mobility_bonus
        - mobility_penalty
    )
    return max(0.0, min(1.0, round(score, 4))), reasons


def _score_advertiser_match(zone: dict[str, Any], advertiser: dict[str, Any], city_context: dict[str, Any]) -> tuple[dict[str, float], list[str], list[str]]:
    zone_audience = set(zone["audience"]) | set(zone["audience_by_time"].get(city_context["time_context"]["time_slot"], []))
    advertiser_audience = set(advertiser["target_audience"])
    shared_audience = zone_audience & advertiser_audience
    audience_match = len(shared_audience) / max(len(advertiser_audience), 1)

    local_event_context = city_context.get("event_influence_by_zone", {}).get(zone["id"], {})
    context_tags = set(city_context["weather"]["impact_tags"])
    context_tags.update(city_context["mobility"]["impact_tags"])
    context_tags.update({city_context["time_context"]["day_type"]})
    if city_context["time_context"]["school_holiday"]:
        context_tags.add("school_holiday")
    context_tags.update(local_event_context.get("impact_tags", []))
    if zone["category"] in {"premium", "business_district", "family_leisure", "transport_hub"}:
        context_tags.add(
            {
                "premium": "premium_zone",
                "business_district": "high_energy_zone",
                "family_leisure": "family_leisure",
                "transport_hub": "station_area",
            }[zone["category"]]
        )

    preferred_contexts = set(advertiser["preferred_contexts"])
    context_overlap = len(context_tags & preferred_contexts) / max(len(preferred_contexts), 1)

    time_slot_fit = 1.0 if advertiser["name"] == "Coca-Cola" and city_context["time_context"]["time_slot"] in {"afternoon", "evening"} else 0.6
    if advertiser["name"] == "OUIGO" and zone["category"] == "transport_hub":
        time_slot_fit = 1.0
    elif advertiser["name"] == "Chanel" and zone["category"] == "premium":
        time_slot_fit = 1.0
    elif advertiser["name"] == "Nike" and zone["category"] == "event_venue":
        time_slot_fit = 1.0
    elif advertiser["name"] == "Parc Asterix" and city_context["time_context"]["day_type"] == "weekend":
        time_slot_fit = 1.0

    exclusions = set(advertiser["exclusions"])
    exclusion_hit = bool(context_tags & exclusions)
    risk_penalty = 1.0 if exclusion_hit else 0.0

    reasons = []
    warnings = []
    if shared_audience:
        reasons.append(f"shared audience: {', '.join(sorted(shared_audience))}")
    if context_overlap:
        reasons.append(f"context match on {len(context_tags & preferred_contexts)} preferred signals")
    if exclusion_hit:
        warnings.append("advertiser exclusion matched current context")

    return {
        "audience_match": round(audience_match, 4),
        "weather_fit": round(1.0 if "good_weather" in context_tags or "hot_weather" in context_tags else 0.5, 4),
        "events_fit": round(context_overlap, 4),
        "mobility_fit": round(1.0 if "high_mobility" in context_tags or "station_area" in context_tags else 0.5, 4),
        "time_slot_fit": round(time_slot_fit, 4),
        "risk_penalty": round(risk_penalty, 4),
    }, reasons, warnings


def score_allocations(
    zones: list[dict[str, Any]],
    advertisers: list[dict[str, Any]],
    city_context: dict[str, Any],
    weights: dict[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    log_entries = []
    zone_scores: dict[str, tuple[float, list[str]]] = {}
    for zone in zones:
        zone_scores[zone["id"]] = _score_zone_attractiveness(zone, city_context)
    log_entries.append({"agent": "zone_analyzer_agent", "status": "completed", "details": {"zone_count": len(zones)}})

    scorecards = []
    for zone in zones:
        zone_attractiveness, zone_reasons = zone_scores[zone["id"]]
        for advertiser in advertisers:
            component_scores, reasons, warnings = _score_advertiser_match(zone, advertiser, city_context)
            total_score = (
                component_scores["audience_match"] * weights["audience_match"]
                + component_scores["weather_fit"] * weights["weather_fit"]
                + component_scores["events_fit"] * weights["events_fit"]
                + component_scores["mobility_fit"] * weights["mobility_fit"]
                + component_scores["time_slot_fit"] * weights["time_slot_fit"]
                + zone_attractiveness * weights["zone_attractiveness"]
                + component_scores["risk_penalty"] * weights["risk_penalty"]
            ) * advertiser["priority"]
            confidence = max(0.35, min(0.97, city_context["confidence"] - 0.15 * component_scores["risk_penalty"] + 0.05 * component_scores["events_fit"]))
            scorecards.append(
                {
                    "zone_id": zone["id"],
                    "zone_name": zone["name"],
                    "advertiser_id": advertiser["id"],
                    "advertiser_name": advertiser["name"],
                    "total_score": round(total_score, 4),
                    "confidence": round(confidence, 4),
                    "component_scores": {
                        **component_scores,
                        "zone_attractiveness": zone_attractiveness,
                    },
                    "reasons": zone_reasons + reasons,
                    "warnings": warnings,
                }
            )
    log_entries.append({"agent": "advertiser_matcher_agent", "status": "completed", "details": {"comparisons": len(scorecards)}})
    return scorecards, log_entries


def headline_match(allocation_plan: dict[str, Any]) -> dict[str, Any] | None:
    """The match the narrative should lead with.

    In single-brand mode that is the focused advertiser's best placement, not the globally
    top-scored one — otherwise a Nike campaign gets summarized around whichever brand scored
    highest. Matches are score-sorted, so the first focus match is its best. Falls back to the
    top match when no focus is set or the focus won no billboard.
    """
    matches = allocation_plan.get("recommended_matches") or allocation_plan.get("ranked_matches") or []
    if not matches:
        return None
    focus = allocation_plan.get("focus_advertiser")
    if focus:
        for match in matches:
            if match["advertiser_name"] == focus:
                return match
    return matches[0]


def allocate_campaigns(
    scorecards: list[dict[str, Any]], focus_advertiser: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_zone: dict[str, dict[str, Any]] = {}
    by_advertiser: dict[str, list[dict[str, Any]]] = {}
    recommended_matches: list[dict[str, Any]] = []
    recommended_by_advertiser: dict[str, int] = {}
    recommended_zone_ids: set[str] = set()
    sorted_scorecards = sorted(scorecards, key=lambda item: item["total_score"], reverse=True)

    def _cap(advertiser_name: str) -> int:
        # Single-brand mode lifts only the focused advertiser's cap; the scoring itself is
        # untouched, so the focus wins panels on merit, not on a distorted score.
        if focus_advertiser and advertiser_name == focus_advertiser:
            return MAX_RECOMMENDED_FOR_FOCUS
        return MAX_RECOMMENDED_PER_ADVERTISER

    for scorecard in sorted_scorecards:
        by_advertiser.setdefault(scorecard["advertiser_name"], [])
        if len(by_advertiser[scorecard["advertiser_name"]]) < 3:
            by_advertiser[scorecard["advertiser_name"]].append(scorecard)
        if scorecard["zone_id"] not in by_zone:
            by_zone[scorecard["zone_id"]] = scorecard
        if len(recommended_matches) >= RECOMMENDED_MATCH_COUNT:
            continue
        advertiser_name = scorecard["advertiser_name"]
        if recommended_by_advertiser.get(advertiser_name, 0) >= _cap(advertiser_name):
            continue
        if scorecard["zone_id"] in recommended_zone_ids:
            continue
        recommended_matches.append(scorecard)
        recommended_by_advertiser[advertiser_name] = recommended_by_advertiser.get(advertiser_name, 0) + 1
        recommended_zone_ids.add(scorecard["zone_id"])

    if len(recommended_matches) < RECOMMENDED_MATCH_COUNT:
        for scorecard in sorted_scorecards:
            if len(recommended_matches) >= RECOMMENDED_MATCH_COUNT:
                break
            if scorecard["zone_id"] in recommended_zone_ids:
                continue
            recommended_matches.append(scorecard)
            recommended_zone_ids.add(scorecard["zone_id"])

    focus_share = recommended_by_advertiser.get(focus_advertiser, 0) if focus_advertiser else 0
    if focus_advertiser:
        summary = (
            f"Single-brand plan focused on {focus_advertiser}: {focus_share} of "
            f"{len(recommended_matches)} billboards, the rest across {len(by_advertiser) - 1} other advertisers."
        )
    else:
        summary = f"Allocated {len(by_zone)} zones across {len(by_advertiser)} advertisers."

    allocation_plan = {
        "ranked_matches": sorted_scorecards[:RECOMMENDED_MATCH_COUNT],
        "recommended_matches": recommended_matches,
        "by_zone": by_zone,
        "by_advertiser": by_advertiser,
        "focus_advertiser": focus_advertiser,
        "summary": summary,
    }
    log_entry = {
        "agent": "campaign_allocator_agent",
        "status": "completed",
        "details": {
            "top_match": allocation_plan["recommended_matches"][0]["advertiser_name"] if allocation_plan["recommended_matches"] else None,
            "allocated_zone_count": len(by_zone),
            "recommended_advertiser_count": len({match["advertiser_name"] for match in recommended_matches}),
            "focus_advertiser": focus_advertiser,
            "focus_billboards": focus_share if focus_advertiser else None,
        },
    }
    return allocation_plan, log_entry
