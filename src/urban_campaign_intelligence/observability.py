"""Run-level observability: correlation id, timings, structured logs, visual trace.

The execution log was previously only a field of the response. It is now also emitted as
structured log records, so the same trace survives once the pipeline runs inside
AgentCore Runtime and lands in CloudWatch.
"""

from __future__ import annotations

import json
import logging
import uuid
from time import perf_counter
from typing import Any

logger = logging.getLogger("urban_campaign_intelligence.run")

# Steps whose duration is worth showing on the visual trace, in pipeline order.
_MERMAID_SKIP_KEYS = {"run_id", "seq", "t_ms", "elapsed_ms"}


def new_run_id() -> str:
    """Short correlation id, readable in a terminal and greppable in logs."""
    return f"run_{uuid.uuid4().hex[:12]}"


class RunTrace:
    """Collects the execution log of one request, stamping order and timings."""

    def __init__(self, run_id: str | None = None, request_mode: str = "unknown") -> None:
        self.run_id = run_id or new_run_id()
        self.request_mode = request_mode
        self.entries: list[dict[str, Any]] = []
        self._start = perf_counter()
        self._last = self._start

    @property
    def elapsed_ms(self) -> float:
        return round((perf_counter() - self._start) * 1000, 1)

    def record(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Stamp one execution-log entry and emit it as a structured log record."""
        now = perf_counter()
        stamped = {
            **entry,
            "run_id": self.run_id,
            "seq": len(self.entries),
            # component is derived from a single table (like phase), not hardcoded per entry,
            # so a step name maps to its owning component in one place.
            "component": _component(entry),
            # start_ms is kept unrounded-derived so a time axis can place bars exactly;
            # t_ms and elapsed_ms stay rounded for readability.
            "start_ms": round((self._last - self._start) * 1000, 3),
            "end_ms": round((now - self._start) * 1000, 3),
            "t_ms": round((now - self._last) * 1000, 1),
            "elapsed_ms": round((now - self._start) * 1000, 1),
        }
        self._last = now
        self.entries.append(stamped)
        logger.info(json.dumps(stamped, default=str))
        return stamped

    def record_all(self, entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            self.record(entry)

    def summary(self) -> dict[str, Any]:
        llm_steps = [e for e in self.entries if (e.get("details") or {}).get("mode") == "llm"]
        tokens = sum((e.get("details") or {}).get("total_tokens") or 0 for e in llm_steps)
        return {
            "run_id": self.run_id,
            "mode": self.request_mode,
            "step_count": len(self.entries),
            "duration_ms": self.elapsed_ms,
            "llm_step_count": len(llm_steps),
            "total_tokens": tokens or None,
        }


def _step_name(entry: dict[str, Any]) -> str:
    return entry.get("step") or entry.get("tool") or entry.get("agent") or "step"


def _owner(entry: dict[str, Any]) -> str:
    """Which layer owns this step — mirrors the boundaries of docs/RUNTIME_MAPPING.md."""
    if entry.get("tool"):
        return "Tools"
    if (entry.get("details") or {}).get("mode") == "llm":
        return "LLM"
    return "Core"


# Which real component runs each step. Single source, like _PHASES; the names match the
# components of docs/RUNTIME_MAPPING.md so the runtime trace mirrors the static map.
_COMPONENTS = {
    "pre_hook": "PreHook",
    "get_weather": "GatewayProvider", "get_events": "GatewayProvider", "get_mobility": "GatewayProvider",
    "weather_agent": "ContextAgents", "events_agent": "ContextAgents", "mobility_agent": "ContextAgents",
    "city_context_builder": "CityContextBuilder",
    "zone_analyzer_agent": "ScoringEngine", "advertiser_matcher_agent": "ScoringEngine",
    "campaign_allocator_agent": "ScoringEngine",
    "review_agent": "ReviewAgent",
    "executive_summary_agent": "ExecutiveSummary",
}


def _component(entry: dict[str, Any]) -> str:
    return _COMPONENTS.get(_step_name(entry), "Other")


def to_mermaid(result: dict[str, Any]) -> str:
    """Render the execution log as a Mermaid sequence diagram, by real component.

    The application service orchestrates: each step is a call from the orchestrator to the
    component that ran it — the runtime counterpart of the static map in RUNTIME_MAPPING.md.
    Wrapped in a fenced block so it pastes straight into Markdown and renders on GitHub.
    """
    entries = result.get("execution_log", [])
    # Distinct components in order of first appearance, each given a short mermaid alias.
    components: list[str] = []
    for entry in entries:
        comp = entry.get("component") or _component(entry)
        if comp not in components:
            components.append(comp)
    alias = {comp: f"C{i}" for i, comp in enumerate(components)}

    lines = ["```mermaid", "sequenceDiagram", "    autonumber", "    participant APP as ApplicationService"]
    for comp in components:
        lines.append(f"    participant {alias[comp]} as {comp}")
    for entry in entries:
        comp = entry.get("component") or _component(entry)
        millis = entry.get("t_ms")
        suffix = f" ({millis} ms)" if millis is not None else ""
        lines.append(f"    APP->>{alias[comp]}: {_step_name(entry)}{suffix}")
        lines.append(f"    {alias[comp]}-->>APP: ok")
    for warning in result.get("city_context", {}).get("warnings", []):
        lines.append(f"    Note over APP: ⚠ {warning[:60]}")
    lines.append("```")
    return "\n".join(lines)


_PHASES = {
    "pre_hook": "Input",
    "get_weather": "Context", "get_events": "Context", "get_mobility": "Context",
    "weather_agent": "Context", "events_agent": "Context", "mobility_agent": "Context",
    "city_context_builder": "Context",
    "zone_analyzer_agent": "Decision", "advertiser_matcher_agent": "Decision",
    "campaign_allocator_agent": "Decision",
    "review_agent": "Output", "executive_summary_agent": "Output",
}


def _phase(entry: dict[str, Any]) -> str:
    """Pipeline phase, used as gantt section. Phases are contiguous by construction,
    unlike the owning layer, which alternates and would produce duplicate sections."""
    return _PHASES.get(_step_name(entry), "Other")


def to_gantt(result: dict[str, Any]) -> str:
    """Render the run on a time axis as a Mermaid gantt chart.

    Unlike the sequence diagram, which only shows ordering, this places each step at
    its real offset with its real duration — the view to use when hunting latency.
    """
    entries = result.get("execution_log", [])
    run = result.get("run", {})
    total_ms = run.get("duration_ms") or 0
    # Sub-millisecond steps collapse to zero-width bars, so plot microseconds when the
    # whole run is short. Deterministic runs are ~2 ms; LLM runs will be seconds.
    scale, unit = (1000, "us") if total_ms < 50 else (1, "ms")
    lines = [
        "```mermaid",
        "gantt",
        f"    title Run {run.get('run_id', '?')} — {total_ms} ms total (axis in {unit})",
        "    dateFormat x",
        "    axisFormat %L",
        "    todayMarker off",
    ]
    current_section = None
    for entry in entries:
        phase = _phase(entry)
        if phase != current_section:
            lines.append(f"    section {phase}")
            current_section = phase
        start = (entry.get("start_ms") or 0) * scale
        elapsed = (entry.get("end_ms") or entry.get("elapsed_ms") or 0) * scale
        # Mermaid needs a non-zero span to draw a bar at all.
        end = max(start + 1, elapsed)
        # The axis is a clock and wraps every 1000 units, so keep the duration in the
        # label: it stays exact whatever the axis shows.
        span = (entry.get("end_ms") or 0) - (entry.get("start_ms") or 0)
        shown = f"{span * scale:.0f}{unit}" if scale > 1 else f"{span:.1f}{unit}"
        label = f"{_step_name(entry)} {shown}"
        lines.append(f"    {label} :{int(round(start))}, {int(round(end))}")
    lines.append("```")
    return "\n".join(lines)


def to_timeline(result: dict[str, Any], width: int = 40) -> str:
    """Compact ASCII timeline, for a terminal rather than a Markdown file."""
    entries = result.get("execution_log", [])
    if not entries:
        return "(no execution log)"
    slowest = max((e.get("t_ms") or 0) for e in entries) or 1
    lines = []
    for entry in entries:
        millis = entry.get("t_ms") or 0
        bar = "█" * max(1, int(width * millis / slowest))
        lines.append(f"  {_owner(entry):5} {_step_name(entry):26} {millis:8.1f} ms {bar}")
    total = entries[-1].get("elapsed_ms")
    lines.append(f"  {'':5} {'TOTAL':26} {total:8.1f} ms")
    return "\n".join(lines)
