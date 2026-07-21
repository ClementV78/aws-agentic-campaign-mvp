"""Structured output contracts for the LLM steps.

Strands turns these Pydantic models into tool specs and validates the answer, so the
call sites no longer hand-check types. The OpenRouter fallback validates against the
same models, which keeps both providers on one contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]


class EventClassification(BaseModel):
    """How the events agent reads one raw event."""

    event_type: str = Field(description="Business taxonomy type for the event.")
    impact_level: RiskLevel = Field(default="medium", description="Expected impact on urban attendance.")
    impact_tags: list[str] = Field(default_factory=lambda: ["events"])
    zone_ids: list[str] = Field(default_factory=list, description="Demonstration zones the event influences.")
    zone_weights: dict[str, float] = Field(default_factory=dict)
    audience_tags: list[str] = Field(default_factory=list)
    active_time_slots: list[str] = Field(default_factory=list)
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)


class AllocationReview(BaseModel):
    """Verdict of the review agent on a candidate allocation."""

    guardrails_passed: bool = True
    hallucination_risk: RiskLevel = "medium"
    saturation_risk: RiskLevel = "medium"
    warnings: list[str] = Field(default_factory=list)
    top_match_summary: str = ""


class ExecutiveSummary(BaseModel):
    """Business-facing summary of a recommendation."""

    executive_summary: str = Field(min_length=1, description="Two to four business-oriented sentences.")
