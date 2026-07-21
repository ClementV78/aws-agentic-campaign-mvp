from __future__ import annotations

import os
from typing import Any

from urban_campaign_intelligence.llm_client import get_llm_client


def review_allocation(city_context: dict[str, Any], allocation_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    review_mode = os.getenv("REVIEW_AGENT_MODE", "heuristic").strip().lower()
    if review_mode == "llm":
        llm_result = _review_allocation_llm(city_context, allocation_plan)
        if llm_result is not None:
            return llm_result

    return _review_allocation_heuristic(city_context, allocation_plan)


def _review_allocation_heuristic(city_context: dict[str, Any], allocation_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    warnings = list(city_context["warnings"])
    recommended_matches = allocation_plan.get("recommended_matches", allocation_plan["ranked_matches"])
    recommended_advertisers = {match["advertiser_name"] for match in recommended_matches[:5]}
    if len(recommended_advertisers) < 3:
        warnings.append("Low advertiser diversity in top recommendations.")

    top_match = recommended_matches[0] if recommended_matches else None
    low_confidence_matches = [match for match in recommended_matches if match["confidence"] < 0.55]
    if low_confidence_matches:
        warnings.append("Some top matches have low confidence and should be treated as indicative only.")

    review = {
        "guardrails_passed": True,
        "hallucination_risk": "low",
        "saturation_risk": "medium" if len(recommended_advertisers) <= 3 else "low",
        "warnings": warnings,
        "top_match_summary": (
            f"{top_match['advertiser_name']} -> {top_match['zone_name']} ({top_match['total_score']})"
            if top_match
            else "No allocation generated."
        ),
    }
    log_entry = {
        "agent": "review_agent",
        "status": "completed",
        "details": {
            "warning_count": len(warnings),
            "hallucination_risk": review["hallucination_risk"],
            "mode": "heuristic",
            "recommended_advertiser_count": len(recommended_advertisers),
        },
    }
    return review, log_entry


def _review_allocation_llm(city_context: dict[str, Any], allocation_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    client = get_llm_client()
    model_override = os.getenv("REVIEW_AGENT_LLM_MODEL") or os.getenv("REVIEW_AGENT_OPENROUTER_MODEL")
    if model_override:
        client = client.with_model(model_override)
    if not client.is_configured():
        return None

    system_prompt = (
        "You are a review agent for an urban campaign recommendation system. "
        "Return strict JSON only. "
        "You must review coherence, identify warnings, estimate hallucination risk, "
        "and summarize the top recommendation briefly."
    )
    user_prompt = (
        "Review the following recommendation output. "
        "Return JSON with keys: guardrails_passed, hallucination_risk, saturation_risk, warnings, top_match_summary. "
        "hallucination_risk and saturation_risk must be one of low, medium, high. "
        f"City context: {city_context}\n"
        f"Allocation summary: {allocation_plan['summary']}\n"
        f"Top ranked matches: {allocation_plan['ranked_matches'][:5]}"
    )

    try:
        payload = client.create_json_completion(system_prompt=system_prompt, user_prompt=user_prompt)
    except ValueError:
        return None

    warnings = payload.get("warnings", [])
    if not isinstance(warnings, list):
        return None

    review = {
        "guardrails_passed": bool(payload.get("guardrails_passed", True)),
        "hallucination_risk": payload.get("hallucination_risk", "medium"),
        "saturation_risk": payload.get("saturation_risk", "medium"),
        "warnings": warnings or list(city_context["warnings"]),
        "top_match_summary": payload.get("top_match_summary", allocation_plan["summary"]),
    }
    log_entry = {
        "agent": "review_agent",
        "status": "completed",
        "details": {
            "warning_count": len(review["warnings"]),
            "hallucination_risk": review["hallucination_risk"],
            "mode": "llm",
            "provider": getattr(client, "provider", "unknown"),
            "model": client.model,
        },
    }
    return review, log_entry
