#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/lib/aws_context.sh"
load_deploy_aws_context "bootstrap"

# Bootstrap is intentionally split into small checks:
# local tooling, repo layout, AWS identity, AgentCore config, then optional tests.
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
AWS_PROFILE="${AWS_PROFILE:-}"
AGENTCORE_PROJECT_DIR="${AGENTCORE_PROJECT_DIR:-${PROJECT_ROOT}/agentcore-project/UrbanCampaignIntelligencePoc}"
AGENTCORE_CONFIG_DIR="${AGENTCORE_CONFIG_DIR:-${AGENTCORE_PROJECT_DIR}/agentcore}"
RUN_LOCAL_TESTS="${RUN_LOCAL_TESTS:-1}"

# Build the AWS CLI invocation once so every later check uses the same profile/region context.
AWS_CMD=(aws)
if [[ -n "${AWS_PROFILE}" ]]; then
  AWS_CMD+=(--profile "${AWS_PROFILE}")
fi
if [[ -n "${AWS_REGION}" ]]; then
  AWS_CMD+=(--region "${AWS_REGION}")
fi

log() {
  printf '[bootstrap] %s\n' "$*"
}

warn() {
  printf '[bootstrap][warn] %s\n' "$*" >&2
}

fail() {
  printf '[bootstrap][error] %s\n' "$*" >&2
  exit 1
}

# Small guard helpers keep the validation steps readable and fail fast with a precise message.
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_file() {
  [[ -f "$1" ]] || fail "Missing required file: $1"
}

require_dir() {
  [[ -d "$1" ]] || fail "Missing required directory: $1"
}

check_core_commands() {
  log "Checking local commands"

  # These commands are the minimum needed by the current Lot 2 path:
  # local tests, AWS checks, artifact packaging, and AgentCore/CDK operations.
  require_cmd python3
  require_cmd aws
  require_cmd zip
  require_cmd node
  require_cmd npm
  require_cmd npx
  require_cmd agentcore
}

check_node_version() {
  log "Checking Node.js version"

  # The vended AgentCore CDK project documents Node.js 20+ as a prerequisite.
  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "${node_major}" =~ ^[0-9]+$ ]] || fail "Unable to parse Node.js version."

  if (( node_major < 20 )); then
    fail "Node.js 20+ is required for the AgentCore CDK project. Current major=${node_major}."
  fi
}

check_repo_layout() {
  log "Checking repository layout"

  # We verify only the files that are structural for the current deploy path.
  # This avoids discovering missing repo prerequisites later in deploy.sh.
  require_dir "${PROJECT_ROOT}/src/urban_campaign_intelligence"
  require_dir "${AGENTCORE_PROJECT_DIR}"
  require_dir "${AGENTCORE_CONFIG_DIR}"
  require_dir "${AGENTCORE_CONFIG_DIR}/cdk"
  require_file "${AGENTCORE_CONFIG_DIR}/agentcore.json"
  require_file "${AGENTCORE_CONFIG_DIR}/aws-targets.json"
  require_file "${AGENTCORE_CONFIG_DIR}/cdk/package.json"
  require_file "${PROJECT_ROOT}/tools/gateway_tool_contracts.json"
  require_file "${PROJECT_ROOT}/tools/scoring_weights.json"
  require_file "${PROJECT_ROOT}/data/scenarios.json"
}

check_python_version() {
  log "Checking Python version"

  # Python is checked explicitly because the local MVP package targets 3.12+.
  python3 - <<'PY'
import sys

major, minor = sys.version_info[:2]
if (major, minor) < (3, 12):
    raise SystemExit("Python 3.12+ is required for the local MVP environment.")

print(f"[bootstrap] Python version OK: {major}.{minor}")
PY
}

check_aws_context() {
  log "Checking AWS context"

  # We resolve caller identity early so failures are obvious before any deploy step.
  [[ -n "${AWS_REGION}" ]] || fail "AWS_REGION or AWS_DEFAULT_REGION must be set."
  enforce_deploy_aws_context "bootstrap"

  local account_id arn
  account_id="$("${AWS_CMD[@]}" sts get-caller-identity --query Account --output text 2>/dev/null)" || \
    fail "Unable to resolve AWS account. Configure credentials or AWS_PROFILE."
  arn="$("${AWS_CMD[@]}" sts get-caller-identity --query Arn --output text 2>/dev/null)" || \
    fail "Unable to resolve AWS caller ARN."

  log "AWS account: ${account_id}"
  log "AWS caller : ${arn}"
  log "AWS region : ${AWS_REGION}"
}

check_agentcore_targets() {
  log "Checking AgentCore deployment targets"

  # An empty targets file is not a bootstrap failure yet, but it explains why live deploy
  # will be skipped later. Keeping it as a warning makes the script useful before first deploy.
  python3 - "${AGENTCORE_CONFIG_DIR}/aws-targets.json" <<'PY'
import json
import sys
from pathlib import Path

targets_path = Path(sys.argv[1])
payload = json.loads(targets_path.read_text(encoding="utf-8"))

if not isinstance(payload, list):
    raise SystemExit("agentcore/aws-targets.json must contain a JSON array.")

print(f"[bootstrap] AgentCore targets configured: {len(payload)}")

if not payload:
    print(
        "[bootstrap][warn] No AgentCore deployment target configured yet. "
        "Live deploy will be skipped until aws-targets.json is filled."
    )
PY
}

check_agentcore_project() {
  log "Validating AgentCore project"
  # This catches invalid names or schema issues before deploy.sh reaches the runtime step.
  (
    cd "${AGENTCORE_PROJECT_DIR}"
    agentcore validate
  )
}

run_local_tests() {
  # Tests stay enabled by default because bootstrap is also the quickest confidence check
  # that the local deterministic path still works before touching AWS.
  if [[ "${RUN_LOCAL_TESTS}" != "1" ]]; then
    warn "Local tests skipped because RUN_LOCAL_TESTS=${RUN_LOCAL_TESTS}"
    return 0
  fi

  log "Running local test suite"
  (
    cd "${PROJECT_ROOT}"
    PYTHONPATH=src python3 -m unittest discover -s tests -v
  )
}

print_summary() {
  log "Bootstrap summary"
  cat <<EOF
AgentCore project dir: ${AGENTCORE_PROJECT_DIR}
AgentCore config dir : ${AGENTCORE_CONFIG_DIR}
AWS profile          : ${AWS_PROFILE:-<default>}
AWS region           : ${AWS_REGION}
Expected AWS account : ${EXPECTED_AWS_ACCOUNT_ID:-<unset>}
Local tests enabled  : ${RUN_LOCAL_TESTS}
EOF
}

main() {
  # Order matters: fail fast on tooling and structure, then AWS access, then project validity.
  check_core_commands
  check_node_version
  check_repo_layout
  check_python_version
  check_aws_context
  check_agentcore_targets
  check_agentcore_project
  run_local_tests
  print_summary
}

main "$@"
