from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _data_root_candidates() -> list[Path]:
    """Where to look for data/ and tools/, most specific first.

    Local dev, the CLI and tests run from the repo, where the package sits at src/<pkg> and the
    data lives two levels up (parents[2]). The deployed AgentCore runtime stages the package into
    the CodeZip at /var/task/<pkg>, with data/ and tools/ beside it (parents[1]) — the repo root
    no longer exists there. An explicit override wins for anything else (e.g. data behind S3 later).
    """
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    override = os.getenv("AGENTCAMPAIGN_DATA_ROOT")
    if override:
        candidates.append(Path(override))
    candidates.extend([here.parents[2], here.parents[1], Path.cwd()])
    return candidates


def load_json(relative_path: str) -> Any:
    for root in _data_root_candidates():
        path = root / relative_path
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
    tried = ", ".join(str(root / relative_path) for root in _data_root_candidates())
    raise FileNotFoundError(f"Could not locate '{relative_path}'. Tried: {tried}")


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

