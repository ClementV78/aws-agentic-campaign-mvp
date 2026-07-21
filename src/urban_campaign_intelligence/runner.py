from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from urban_campaign_intelligence.local_agent import CampaignRequest, LocalRequestMapper, UrbanCampaignStrandsAgent
from urban_campaign_intelligence.observability import to_gantt, to_mermaid, to_timeline


def run_scenario(scenario_id: str) -> dict[str, Any]:
    agent = UrbanCampaignStrandsAgent()
    return agent.handle_request(CampaignRequest(mode="scenario", scenario_id=scenario_id))


def run_request(request: CampaignRequest) -> dict[str, Any]:
    agent = UrbanCampaignStrandsAgent()
    return agent.handle_request(request)


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
    request_group = parser.add_mutually_exclusive_group(required=True)
    request_group.add_argument("--scenario", help="Scenario id from data/scenarios.json")
    request_group.add_argument("--datetime", help="ISO datetime for live Paris mode")
    parser.add_argument("--city", default="Paris", help="City for live mode. Currently only Paris is supported.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--trace", action="store_true", help="Print a timeline of the run")
    parser.add_argument("--trace-mermaid", action="store_true", help="Print the run as a Mermaid sequence diagram")
    parser.add_argument("--trace-gantt", action="store_true", help="Print the run as a Mermaid gantt chart on a time axis")
    parser.add_argument("--verbose", action="store_true", help="Emit the structured execution log on stderr")
    parser.add_argument("--summary", action="store_true", help="Print a compact human-readable summary")
    parser.add_argument("--output", help="Write full JSON result to a file")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    request = LocalRequestMapper.from_cli_args(args)
    result = run_request(request)
    output_path = None
    if args.output:
        output_path = write_result(result, args.output)

    if args.trace or args.trace_mermaid or args.trace_gantt:
        run = result.get("run", {})
        print(f"run_id={run.get('run_id')} mode={run.get('mode')} "
              f"steps={run.get('step_count')} duration={run.get('duration_ms')} ms "
              f"tokens={run.get('total_tokens')}")
        if args.trace_gantt:
            print(to_gantt(result))
        elif args.trace_mermaid:
            print(to_mermaid(result))
        else:
            print(to_timeline(result))
        if not (args.pretty or args.summary or args.output):
            return

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
