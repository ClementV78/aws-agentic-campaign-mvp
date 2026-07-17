from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_json(relative_path: str) -> Any:
    with (PROJECT_ROOT / relative_path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_zones() -> list[dict[str, Any]]:
    return load_json("data/zones.json")


def load_advertisers() -> list[dict[str, Any]]:
    return load_json("data/advertisers.json")


def load_scenarios() -> list[dict[str, Any]]:
    return load_json("data/scenarios.json")


def load_weights() -> dict[str, float]:
    return load_json("tools/scoring_weights.json")


def get_scenario_by_id(scenario_id: str) -> dict[str, Any]:
    for scenario in load_scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    available = ", ".join(s["id"] for s in load_scenarios())
    raise ValueError(f"Unknown scenario_id '{scenario_id}'. Available: {available}")

