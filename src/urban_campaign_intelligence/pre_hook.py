from __future__ import annotations

from datetime import datetime
from typing import Any


def derive_time_slot(hour: int) -> str:
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "night"


def run_pre_hook(scenario: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dt = datetime.fromisoformat(scenario["datetime"])
    calendar = scenario.get("calendar", scenario.get("signals", {}))
    scenario_inputs = scenario.get("inputs", scenario.get("signals", {}))
    normalized_input = {
        "scenario_id": scenario["id"],
        "city": scenario["city"].strip(),
        "datetime": dt.isoformat(),
        "inputs": scenario_inputs,
    }
    time_context = {
        "day_type": calendar["day_type"],
        "time_slot": derive_time_slot(dt.hour),
        "school_holiday": calendar["school_holiday"],
    }
    execution_log = [
        {
            "step": "pre_hook",
            "status": "completed",
            "details": {
                "normalized_city": normalized_input["city"],
                "normalized_datetime": normalized_input["datetime"],
                "time_slot": time_context["time_slot"],
            },
        }
    ]
    return {"input": normalized_input, "time_context": time_context}, execution_log
