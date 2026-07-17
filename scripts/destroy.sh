#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/lib/aws_context.sh"
load_deploy_aws_context "destroy"

APP_NAME="${APP_NAME:-urban-campaign-intelligence}"
DEPLOY_STAGE="${DEPLOY_STAGE:-poc}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
AWS_PROFILE="${AWS_PROFILE:-}"
OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_ROOT}/outputs/deploy}"
MANIFEST_PATH="${MANIFEST_PATH:-${OUTPUT_DIR}/deployment-manifest.json}"
DEPLOY_OUTPUTS_PATH="${DEPLOY_OUTPUTS_PATH:-${OUTPUT_DIR}/deploy-outputs.json}"
AGENTCORE_PROJECT_DIR="${AGENTCORE_PROJECT_DIR:-${PROJECT_ROOT}/agentcore-project/UrbanCampaignIntelligencePoc}"
AGENTCORE_DESTROY_ENABLED="${AGENTCORE_DESTROY_ENABLED:-1}"
REMOVE_S3_BUCKET="${REMOVE_S3_BUCKET:-1}"
REMOVE_LOCAL_OUTPUTS="${REMOVE_LOCAL_OUTPUTS:-0}"
DRY_RUN="${DRY_RUN:-0}"

AWS_CMD=(aws)
if [[ -n "${AWS_PROFILE}" ]]; then
  AWS_CMD+=(--profile "${AWS_PROFILE}")
fi
if [[ -n "${AWS_REGION}" ]]; then
  AWS_CMD+=(--region "${AWS_REGION}")
fi

S3_BUCKET=""
S3_PREFIX="deploy"

log() {
  printf '[destroy] %s\n' "$*"
}

warn() {
  printf '[destroy][warn] %s\n' "$*" >&2
}

fail() {
  printf '[destroy][error] %s\n' "$*" >&2
  exit 1
}

run_cmd() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[destroy][dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

check_prereqs() {
  log "Loading destroy configuration"
  [[ -n "${AWS_REGION}" ]] || fail "AWS_REGION or AWS_DEFAULT_REGION must be set."
  require_cmd aws
  require_cmd python3
  enforce_deploy_aws_context "destroy"
}

resolve_from_outputs() {
  if [[ -f "${DEPLOY_OUTPUTS_PATH}" ]]; then
    log "Reading destroy context from ${DEPLOY_OUTPUTS_PATH}"
    mapfile -t DEPLOY_FIELDS < <(
      python3 - "${DEPLOY_OUTPUTS_PATH}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in ("s3_bucket", "s3_prefix", "agentcore_project_dir"):
    value = payload.get(key, "")
    print("" if value is None else value)
PY
    )
    S3_BUCKET="${DEPLOY_FIELDS[0]:-}"
    S3_PREFIX="${DEPLOY_FIELDS[1]:-deploy}"
    if [[ -n "${DEPLOY_FIELDS[2]:-}" ]]; then
      AGENTCORE_PROJECT_DIR="${DEPLOY_FIELDS[2]}"
    fi
    return 0
  fi

  if [[ -f "${MANIFEST_PATH}" ]]; then
    log "Reading destroy context from ${MANIFEST_PATH}"
    mapfile -t MANIFEST_FIELDS < <(
      python3 - "${MANIFEST_PATH}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in ("s3_bucket", "agentcore_project_dir"):
    value = payload.get(key, "")
    print("" if value is None else value)
PY
    )
    S3_BUCKET="${MANIFEST_FIELDS[0]:-}"
    if [[ -n "${MANIFEST_FIELDS[1]:-}" ]]; then
      AGENTCORE_PROJECT_DIR="${MANIFEST_FIELDS[1]}"
    fi
  fi
}

destroy_agentcore_runtime() {
  [[ "${AGENTCORE_DESTROY_ENABLED}" == "1" ]] || {
    warn "AgentCore destroy disabled"
    return 0
  }

  if [[ ! -d "${AGENTCORE_PROJECT_DIR}/agentcore/cdk" ]]; then
    warn "AgentCore CDK directory not found at ${AGENTCORE_PROJECT_DIR}/agentcore/cdk; skipping runtime teardown"
    return 0
  fi

  require_cmd npx

  log "Destroying AgentCore/CDK resources from ${AGENTCORE_PROJECT_DIR}/agentcore/cdk"
  (
    cd "${AGENTCORE_PROJECT_DIR}/agentcore/cdk"
    run_cmd npx cdk destroy --force
  )
}

destroy_s3_artifacts() {
  [[ "${REMOVE_S3_BUCKET}" == "1" ]] || {
    warn "S3 bucket deletion disabled"
    return 0
  }

  if [[ -z "${S3_BUCKET}" ]]; then
    warn "No S3 bucket resolved from deploy outputs or manifest; skipping S3 cleanup"
    return 0
  fi

  log "Removing deployment artifacts from s3://${S3_BUCKET}/${S3_PREFIX}/"
  run_cmd "${AWS_CMD[@]}" s3 rm "s3://${S3_BUCKET}/${S3_PREFIX}/" --recursive

  log "Removing remaining objects from s3://${S3_BUCKET}/"
  run_cmd "${AWS_CMD[@]}" s3 rm "s3://${S3_BUCKET}/" --recursive

  log "Deleting bucket ${S3_BUCKET}"
  run_cmd "${AWS_CMD[@]}" s3api delete-bucket --bucket "${S3_BUCKET}"
}

cleanup_local_outputs() {
  [[ "${REMOVE_LOCAL_OUTPUTS}" == "1" ]] || return 0

  log "Removing local deployment outputs"
  run_cmd rm -rf "${OUTPUT_DIR}"
}

print_summary() {
  log "Destroy summary"
  cat <<EOF
AgentCore project dir: ${AGENTCORE_PROJECT_DIR}
S3 bucket: ${S3_BUCKET:-<unknown>}
S3 prefix: ${S3_PREFIX}
Deploy outputs: ${DEPLOY_OUTPUTS_PATH}
Manifest: ${MANIFEST_PATH}
AGENTCORE_DESTROY_ENABLED: ${AGENTCORE_DESTROY_ENABLED}
REMOVE_S3_BUCKET: ${REMOVE_S3_BUCKET}
REMOVE_LOCAL_OUTPUTS: ${REMOVE_LOCAL_OUTPUTS}
Expected AWS account: ${EXPECTED_AWS_ACCOUNT_ID:-<unset>}
EOF
}

main() {
  check_prereqs
  resolve_from_outputs
  destroy_agentcore_runtime
  destroy_s3_artifacts
  cleanup_local_outputs
  print_summary
}

main "$@"
