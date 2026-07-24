"""Run-level observability: correlation id, timings, structured logs, visual trace.

The execution log was previously only a field of the response. It is now also emitted as
structured log records, so the same trace survives once the pipeline runs inside
AgentCore Runtime and lands in CloudWatch.
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from time import perf_counter
from typing import Any

logger = logging.getLogger("urban_campaign_intelligence.run")

# Steps whose duration is worth showing on the visual trace, in pipeline order.
_MERMAID_SKIP_KEYS = {"run_id", "seq", "t_ms", "elapsed_ms"}

# Per-request context set by the runtime front-end (main.py) from the AgentCore RequestContext.
# It rides a contextvar so RunTrace can read it without threading it through every call site;
# the runtime copies the context into its worker thread, so the value propagates.
_REQUEST_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "ucp_request_context", default={}
)


def set_request_context(*, session_id: str | None = None) -> None:
    """Record the AgentCore session id for the current request (best-effort, optional)."""
    _REQUEST_CONTEXT.set({"session_id": session_id})


def _correlation_ids() -> dict[str, Any]:
    """Ids that join our structured logs to the AgentCore / X-Ray GenAI trace.

    ``aws_trace_id`` comes from the ambient OpenTelemetry span the runtime opens for the request;
    ``session_id`` from the runtime context. Both are absent locally (no OTEL, no runtime) and are
    simply omitted then — this stays a pure best-effort correlation, never a hard dependency.
    """
    ids: dict[str, Any] = {}
    session_id = _REQUEST_CONTEXT.get().get("session_id")
    if session_id:
        ids["session_id"] = session_id
    try:
        from opentelemetry import trace as _otel_trace

        span_context = _otel_trace.get_current_span().get_span_context()
        if getattr(span_context, "trace_id", 0):
            ids["aws_trace_id"] = format(span_context.trace_id, "032x")
            ids["aws_span_id"] = format(span_context.span_id, "016x")
    except Exception:
        pass
    return ids


def _otel_pipeline_tracer() -> tuple[Any, Any] | None:
    """(tracer, parent_context) for emitting decision-layer steps as OTEL child spans.

    The parent is the request span AgentCore opened (POST /invocations), so our spans land in the
    same X-Ray trace tree, as siblings of the agent span. Returns None when OpenTelemetry is not
    active (local runs) — child-span emission then simply does not happen.
    """
    try:
        from opentelemetry import trace as _otel_trace

        current = _otel_trace.get_current_span()
        if not getattr(current.get_span_context(), "trace_id", 0):
            return None
        parent_context = _otel_trace.set_span_in_context(current)
        return _otel_trace.get_tracer("urban_campaign_intelligence.runtrace"), parent_context
    except Exception:
        return None


def new_run_id() -> str:
    """Short correlation id, readable in a terminal and greppable in logs."""
    return f"run_{uuid.uuid4().hex[:12]}"


class RunTrace:
    """Collects the execution log of one request, stamping order and timings."""

    def __init__(self, run_id: str | None = None, request_mode: str = "unknown") -> None:
        self.run_id = run_id or new_run_id()
        self.request_mode = request_mode
        self.entries: list[dict[str, Any]] = []
        # Captured once at trace start: the AgentCore trace/session ids for this request, so every
        # log line and the summary can be pivoted to the X-Ray GenAI trace of the same run.
        self.correlation = _correlation_ids()
        # Decision-layer steps are also emitted as OTEL child spans (when a runtime trace exists),
        # grouped under one "deterministic_pipeline" span so they read as a phase after the agent —
        # not as parallel branches off the request root.
        self._otel = _otel_pipeline_tracer()
        self._pipeline: tuple[Any, Any] | None = None  # (span, context) of the wrapping span
        self._pipeline_end_ns: int | None = None
        self._start = perf_counter()
        self._wall_start_ns = time.time_ns()
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
            **self.correlation,
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
        self._emit_span(stamped)
        return stamped

    def _emit_span(self, stamped: dict[str, Any]) -> None:
        """Emit one decision-layer step as an OTEL child span, timed to match the log entry.

        Skips what AgentCore already traces natively — the tool calls and the agent round-trip —
        so only the layer invisible to X-Ray (pre_hook, context agents, scoring, allocation, review,
        summary) is added. Never raises: observability must not break a request.
        """
        if not self._otel or stamped.get("tool") or stamped.get("step") == "orchestrator_agent":
            return
        try:
            from opentelemetry import trace as _otel_trace

            tracer, root_context = self._otel
            start_ns = self._wall_start_ns + int(stamped["start_ms"] * 1_000_000)
            end_ns = self._wall_start_ns + int(stamped["end_ms"] * 1_000_000)
            # Open the wrapping span on the first decision step, parented to the request span; the
            # individual steps then nest under it rather than under the request root.
            if self._pipeline is None:
                pipeline_span = tracer.start_span("deterministic_pipeline", context=root_context, start_time=start_ns)
                pipeline_span.set_attribute("ucp.component", "DeterministicPipeline")
                self._pipeline = (pipeline_span, _otel_trace.set_span_in_context(pipeline_span))
            _, pipeline_context = self._pipeline
            span = tracer.start_span(_step_name(stamped), context=pipeline_context, start_time=start_ns)
            span.set_attribute("ucp.component", stamped.get("component", "Other"))
            span.set_attribute("ucp.phase", _phase(stamped))
            for key in ("mode", "provider_mode", "focus_advertiser", "total_tokens", "event_count"):
                value = (stamped.get("details") or {}).get(key)
                if value is not None:
                    span.set_attribute(f"ucp.{key}", value)
            span.end(end_time=end_ns)
            self._pipeline_end_ns = end_ns
        except Exception:
            pass

    def _close_pipeline_span(self) -> None:
        """Close the wrapping deterministic_pipeline span once all steps are recorded."""
        if self._pipeline is not None:
            try:
                self._pipeline[0].end(end_time=self._pipeline_end_ns)
            except Exception:
                pass
            self._pipeline = None

    def record_all(self, entries: list[dict[str, Any]]) -> None:
        for entry in entries:
            self.record(entry)

    def summary(self) -> dict[str, Any]:
        self._close_pipeline_span()
        llm_steps = [e for e in self.entries if (e.get("details") or {}).get("mode") == "llm"]
        tokens = sum((e.get("details") or {}).get("total_tokens") or 0 for e in llm_steps)
        return {
            "run_id": self.run_id,
            **self.correlation,
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
    "orchestrator_agent": "UrbanCampaignStrandsAgent",
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
    "orchestrator_agent": "Input",
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


def _gantt_bars(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse consecutive steps of the same component into one bar per component.

    A full run is ~12 steps; one bar each is too dense to read. Steps of one component are
    contiguous (like phases), so merging them keeps the chart to one bar per component — the
    orchestrator agent, being its own component, still stands out. Each bar keeps the real
    start of its first step and end of its last, so offsets and spans stay exact.
    """
    bars: list[dict[str, Any]] = []
    for entry in entries:
        comp = entry.get("component") or _component(entry)
        phase = _phase(entry)
        start = entry.get("start_ms") or 0
        end = entry.get("end_ms") or entry.get("elapsed_ms") or 0
        if bars and bars[-1]["component"] == comp and bars[-1]["phase"] == phase:
            bars[-1]["end_ms"] = end
        else:
            bars.append({"component": comp, "phase": phase, "start_ms": start, "end_ms": end})
    return bars


def to_gantt(result: dict[str, Any]) -> str:
    """Render the run on a time axis as a Mermaid gantt chart.

    Unlike the sequence diagram, which only shows ordering, this places each component at
    its real offset with its real duration — the view to use when hunting latency. Steps are
    aggregated by component (one bar each) so the chart stays readable on long runs.
    """
    bars = _gantt_bars(result.get("execution_log", []))
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
    for bar in bars:
        if bar["phase"] != current_section:
            lines.append(f"    section {bar['phase']}")
            current_section = bar["phase"]
        start = bar["start_ms"] * scale
        # Mermaid needs a non-zero span to draw a bar at all.
        end = max(start + 1, bar["end_ms"] * scale)
        # The axis is a clock and wraps every 1000 units, so keep the duration in the
        # label: it stays exact whatever the axis shows.
        span = bar["end_ms"] - bar["start_ms"]
        shown = f"{span * scale:.0f}{unit}" if scale > 1 else f"{span:.1f}{unit}"
        lines.append(f"    {bar['component']} {shown} :{int(round(start))}, {int(round(end))}")
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
