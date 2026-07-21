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


def to_mermaid(result: dict[str, Any]) -> str:
    """Render the execution log of a run as a Mermaid sequence diagram.

    Wrapped in a fenced block so it pastes straight into Markdown and renders on
    GitHub; without the fence the diagram collapses into a paragraph.
    """
    entries = result.get("execution_log", [])
    lines = [
        "```mermaid",
        "sequenceDiagram",
        "    autonumber",
        "    participant C as Core",
        "    participant T as Tools",
        "    participant L as LLM",
    ]
    actor = {"Core": "C", "Tools": "T", "LLM": "L"}
    for entry in entries:
        target = actor[_owner(entry)]
        label = _step_name(entry)
        millis = entry.get("t_ms")
        suffix = f" ({millis} ms)" if millis is not None else ""
        if target == "C":
            lines.append(f"    C->>C: {label}{suffix}")
        else:
            lines.append(f"    C->>{target}: {label}{suffix}")
            lines.append(f"    {target}-->>C: ok")
    warnings = result.get("city_context", {}).get("warnings", [])
    for warning in warnings:
        lines.append(f"    Note over C: ⚠ {warning[:60]}")
    lines.append("```")
    return "\n".join(lines)


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
        owner = _owner(entry)
        if owner != current_section:
            lines.append(f"    section {owner}")
            current_section = owner
        start = (entry.get("start_ms") or 0) * scale
        elapsed = (entry.get("end_ms") or entry.get("elapsed_ms") or 0) * scale
        # Mermaid needs a non-zero span to draw a bar at all.
        end = max(start + 1, elapsed)
        lines.append(f"    {_step_name(entry)} :{int(round(start))}, {int(round(end))}")
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
