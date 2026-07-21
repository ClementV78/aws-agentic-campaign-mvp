from __future__ import annotations

import os
from typing import Any

from urban_campaign_intelligence.llm_client import get_llm_client
from urban_campaign_intelligence.llm_schemas import ExecutiveSummary


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
    summary = {"text": text, "mode": "deterministic", "provider": "none", "model": None}
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
    client = get_llm_client()
    model_override = os.getenv("EXECUTIVE_SUMMARY_LLM_MODEL") or os.getenv("EXECUTIVE_SUMMARY_OPENROUTER_MODEL")
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
        result = client.create_structured_output(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_model=ExecutiveSummary,
        )
    except ValueError:
        return None

    text = result.executive_summary.strip()
    if not text:
        return None

    summary = {"text": text, "mode": "llm", "provider": getattr(client, "provider", "unknown"), "model": client.model}
    log_entry = {
        "agent": "executive_summary_agent",
        "status": "completed",
        "details": {"mode": "llm", "provider": getattr(client, "provider", "unknown"), "model": client.model, "text_length": len(text)},
    }
    return summary, log_entry
