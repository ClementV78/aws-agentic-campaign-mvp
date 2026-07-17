#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-outputs/demo}"

SCENARIOS=(
  heatwave_saturday
  concert_bercy
  transport_strike
  fashion_week
  school_holiday_departure
)

mkdir -p "${OUTPUT_DIR}"

for scenario in "${SCENARIOS[@]}"; do
  echo "=== ${scenario} ==="
  PYTHONPATH=src python -m urban_campaign_intelligence.runner \
    --scenario "${scenario}" \
    --summary \
    --output "${OUTPUT_DIR}/${scenario}.json"
  echo
done
