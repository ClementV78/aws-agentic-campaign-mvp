from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from urban_campaign_intelligence.city_context import build_city_context
from urban_campaign_intelligence.context_agents import (
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
from urban_campaign_intelligence.pre_hook import run_pre_hook
from urban_campaign_intelligence.review import review_allocation
from urban_campaign_intelligence.scoring import allocate_campaigns, score_allocations
from urban_campaign_intelligence.gateway_tools import GatewayProvider
from urban_campaign_intelligence.llm_client import OpenRouterClient


def _get_scenario_inputs(scenario: dict[str, Any]) -> dict[str, Any]:
    if "inputs" in scenario:
        return scenario["inputs"]
    signals = scenario.get("signals", {})
    return {
        "weather": {"mode": "mock", "raw_condition": signals.get("weather", "clear")},
        "events": [{"mode": "mock", "event_type": event_type} for event_type in signals.get("events", [])],
        "mobility": {"mode": "mock", "network_status": signals.get("mobility", "normal")},
    }


def run_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = get_scenario_by_id(scenario_id)
    zones = load_zones()
    advertisers = load_advertisers()
    weights = load_weights()
    gateway_provider = GatewayProvider()
    scenario_inputs = _get_scenario_inputs(scenario)

    execution_log: list[dict[str, Any]] = []

    pre_hook_output, pre_hook_log = run_pre_hook(scenario)
    execution_log.extend(pre_hook_log)

    weather_payload = gateway_provider.get_weather(
        city=scenario["city"],
        datetime_iso=scenario["datetime"],
        weather_key=scenario_inputs.get("weather", {}).get("raw_condition"),
        weather_input=scenario_inputs.get("weather"),
    )
    events_payload = gateway_provider.get_events(
        city=scenario["city"],
        datetime_iso=scenario["datetime"],
        event_types=[event.get("event_type", "generic_event") for event in scenario_inputs.get("events", [])],
        event_inputs=scenario_inputs.get("events", []),
    )
    mobility_payload = gateway_provider.get_mobility(
        city=scenario["city"],
        datetime_iso=scenario["datetime"],
        mobility_key=scenario_inputs.get("mobility", {}).get("network_status"),
        mobility_input=scenario_inputs.get("mobility"),
    )

    execution_log.extend(
        [
            {
                "tool": "get_weather",
                "status": "completed",
                "details": {
                    "provider": weather_payload["provider"],
                    "provider_mode": weather_payload.get("provider_mode", "mock"),
                    "fallback": weather_payload.get("provider_fallback"),
                    "raw_condition": weather_payload["raw_condition"],
                },
            },
            {
                "tool": "get_events",
                "status": "completed",
                "details": {
                    "provider": events_payload["events"][0]["provider"] if events_payload["events"] else "mock_scenarios",
                    "provider_mode": events_payload.get("provider_mode", "real_or_mock"),
                    "fallback": events_payload.get("provider_fallback"),
                    "event_count": len(events_payload["events"]),
                },
            },
            {
                "tool": "get_mobility",
                "status": "completed",
                "details": {
                    "provider": mobility_payload["provider"],
                    "provider_mode": mobility_payload.get("provider_mode", "mock"),
                    "fallback": mobility_payload.get("provider_fallback"),
                    "network_status": mobility_payload["network_status"],
                },
            },
        ]
    )

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
        },
        "city_context": city_context,
        "allocation_plan": allocation_plan,
        "review": review,
        "executive_summary": executive_summary,
        "execution_log": execution_log,
    }


def generate_executive_summary(
    scenario: dict[str, Any],
    city_context: dict[str, Any],
    allocation_plan: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    mode = os.getenv("EXECUTIVE_SUMMARY_MODE", "deterministic").strip().lower()
    if mode == "llm":
        llm_result = _generate_executive_summary_llm(
            scenario=scenario,
            city_context=city_context,
            allocation_plan=allocation_plan,
            review=review,
        )
        if llm_result is not None:
            return llm_result
    return _generate_executive_summary_deterministic(scenario, city_context, allocation_plan, review)


def _generate_executive_summary_deterministic(
    scenario: dict[str, Any],
    city_context: dict[str, Any],
    allocation_plan: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    recommended_matches = allocation_plan.get("recommended_matches", allocation_plan["ranked_matches"])
    top_match = recommended_matches[0] if recommended_matches else None
    event_names = [event.get("display_name") or event.get("type", "event") for event in city_context["events"][:2]]
    event_fragment = ", ".join(event_names) if event_names else "no major event"
    if top_match is None:
        text = (
            f"{scenario['name']} in {scenario['city']} shows no actionable allocation. "
            f"Context remained {city_context['weather']['summary']} with {city_context['mobility']['global_status']} mobility."
        )
    else:
        text = (
            f"{scenario['name']} in {scenario['city']} favors {top_match['advertiser_name']} on {top_match['zone_name']}. "
            f"The recommendation is driven by {city_context['weather']['summary']} weather, "
            f"{city_context['mobility']['global_status']} mobility, and {event_fragment}. "
            f"Overall confidence is {city_context['confidence']} with {review['hallucination_risk']} hallucination risk."
        )
    summary = {"text": text, "mode": "deterministic", "model": None}
    log_entry = {
        "agent": "executive_summary_agent",
        "status": "completed",
        "details": {"mode": "deterministic", "text_length": len(text)},
    }
    return summary, log_entry


def _generate_executive_summary_llm(
    scenario: dict[str, Any],
    city_context: dict[str, Any],
    allocation_plan: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    client = OpenRouterClient()
    model_override = os.getenv("EXECUTIVE_SUMMARY_OPENROUTER_MODEL")
    if model_override:
        client = client.with_model(model_override)
    if not client.is_configured():
        return None

    recommended_matches = allocation_plan.get("recommended_matches", allocation_plan["ranked_matches"])[:3]
    system_prompt = (
        "You write concise executive summaries for a contextual campaign allocation demo. "
        "Return strict JSON only with one key: executive_summary. "
        "Write 2 to 4 sentences, business-oriented, concrete, and avoid hype."
    )
    user_prompt = (
        f"Scenario: {scenario['name']} in {scenario['city']} at {scenario['datetime']}\n"
        f"City context: {city_context}\n"
        f"Top recommendations: {recommended_matches}\n"
        f"Review: {review}\n"
        "Summarize the business rationale, the dominant contextual signals, and any caution worth mentioning."
    )
    try:
        payload = client.create_json_completion(system_prompt=system_prompt, user_prompt=user_prompt)
    except ValueError:
        return None

    text = payload.get("executive_summary")
    if not isinstance(text, str) or not text.strip():
        return None

    summary = {"text": text.strip(), "mode": "llm", "model": client.model}
    log_entry = {
        "agent": "executive_summary_agent",
        "status": "completed",
        "details": {"mode": "llm", "model": client.model, "text_length": len(text.strip())},
    }
    return summary, log_entry


def format_summary(result: dict[str, Any]) -> str:
    scenario = result["scenario"]
    city_context = result["city_context"]
    allocation_plan = result["allocation_plan"]
    review = result["review"]
    executive_summary = result.get("executive_summary")

    top_matches = allocation_plan.get("recommended_matches", allocation_plan["ranked_matches"])[:3]
    top_match_lines = [
        (
            f"- {match['advertiser_name']} -> {match['zone_name']} "
            f"(score={match['total_score']}, confidence={match['confidence']})"
        )
        for match in top_matches
    ]
    if not top_match_lines:
        top_match_lines = ["- No recommendation generated."]

    warnings = review["warnings"][:5]
    warning_lines = [f"- {warning}" for warning in warnings] if warnings else ["- None"]

    weather_summary = city_context["weather"]["summary"]
    mobility_status = city_context["mobility"]["global_status"]
    event_names = [
        event.get("display_name") or event.get("name") or event.get("type", "unknown_event")
        for event in city_context["events"][:3]
    ]
    event_summary = ", ".join(event_names) if event_names else "none"

    lines = [
        f"Scenario: {scenario['id']} | {scenario['name']}",
        f"City: {scenario['city']} | Datetime: {scenario['datetime']}",
        (
            "Context: "
            f"time_slot={city_context['time_context']['time_slot']}, "
            f"day_type={city_context['time_context']['day_type']}, "
            f"weather={weather_summary}, "
            f"mobility={mobility_status}, "
            f"events={event_summary}"
        ),
        f"Confidence: {city_context['confidence']}",
        (
            f"Allocation: {allocation_plan['summary']} "
            f"(recommended_top={len(allocation_plan.get('recommended_matches', []))})"
        ),
        "Top recommendations:",
        *top_match_lines,
        "Executive summary:",
        f"- {(executive_summary or {}).get('text', 'Not generated.')}",
        (
            "Review: "
            f"guardrails_passed={review['guardrails_passed']}, "
            f"hallucination_risk={review['hallucination_risk']}, "
            f"saturation_risk={review['saturation_risk']}"
        ),
        "Warnings:",
        *warning_lines,
    ]
    return "\n".join(lines)


def write_result(result: dict[str, Any], output_path: str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Urban Campaign Intelligence MVP.")
    parser.add_argument("--scenario", required=True, help="Scenario id from data/scenarios.json")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--summary", action="store_true", help="Print a compact human-readable summary")
    parser.add_argument("--output", help="Write full JSON result to a file")
    args = parser.parse_args()

    result = run_scenario(args.scenario)
    output_path = None
    if args.output:
        output_path = write_result(result, args.output)

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.summary or args.output:
        print(format_summary(result))
        if output_path is not None:
            print(f"\nFull output written to: {output_path}")
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
