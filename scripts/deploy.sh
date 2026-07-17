#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/lib/aws_context.sh"
load_deploy_aws_context "deploy"

# This deploy script is intentionally lightweight:
# it prepares shared artifacts and context, then delegates runtime creation to AgentCore/CDK.
APP_NAME="${APP_NAME:-urban-campaign-intelligence}"
DEPLOY_STAGE="${DEPLOY_STAGE:-poc}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
AWS_PROFILE="${AWS_PROFILE:-}"
PROJECT_TAG_OWNER="${PROJECT_TAG_OWNER:-xclem}"
OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_ROOT}/outputs/deploy}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-${OUTPUT_DIR}/artifacts}"
MANIFEST_PATH="${MANIFEST_PATH:-${OUTPUT_DIR}/deployment-manifest.json}"
DEPLOY_OUTPUTS_PATH="${DEPLOY_OUTPUTS_PATH:-${OUTPUT_DIR}/deploy-outputs.json}"
AGENTCORE_STATUS_PATH="${AGENTCORE_STATUS_PATH:-${OUTPUT_DIR}/agentcore-status.txt}"
AGENTCORE_PROJECT_DIR="${AGENTCORE_PROJECT_DIR:-${PROJECT_ROOT}/agentcore-project/UrbanCampaignIntelligencePoc}"
AGENTCORE_CONFIG_DIR="${AGENTCORE_CONFIG_DIR:-${AGENTCORE_PROJECT_DIR}/agentcore}"
AGENTCORE_TARGET_NAME="${AGENTCORE_TARGET_NAME:-default}"
ENABLE_AGENTCORE_DEPLOY="${ENABLE_AGENTCORE_DEPLOY:-1}"
ENABLE_SMOKE_TEST="${ENABLE_SMOKE_TEST:-0}"
SMOKE_SCENARIO="${SMOKE_SCENARIO:-fashion_week}"
SMOKE_ENDPOINT_URL="${SMOKE_ENDPOINT_URL:-}"
DRY_RUN="${DRY_RUN:-0}"

# Build the AWS CLI invocation once so every command uses the same profile and region.
AWS_CMD=(aws)
if [[ -n "${AWS_PROFILE}" ]]; then
  AWS_CMD+=(--profile "${AWS_PROFILE}")
fi
if [[ -n "${AWS_REGION}" ]]; then
  AWS_CMD+=(--region "${AWS_REGION}")
fi

ACCOUNT_ID=""
RESOURCE_PREFIX=""
S3_BUCKET=""
S3_PREFIX=""

log() {
  printf '[deploy] %s\n' "$*"
}

warn() {
  printf '[deploy][warn] %s\n' "$*" >&2
}

fail() {
  printf '[deploy][error] %s\n' "$*" >&2
  exit 1
}

# All cloud-changing commands go through this wrapper so dry-run stays predictable and readable.
run_cmd() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[deploy][dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_file() {
  [[ -f "$1" ]] || fail "Missing required file: $1"
}

require_dir() {
  [[ -d "$1" ]] || fail "Missing required directory: $1"
}

load_config() {
  log "Loading deploy configuration"

  # Region is required early because bucket naming and AWS CLI context depend on it.
  [[ -n "${AWS_REGION}" ]] || fail "AWS_REGION or AWS_DEFAULT_REGION must be set."

  mkdir -p "${OUTPUT_DIR}" "${ARTIFACTS_DIR}"
  RESOURCE_PREFIX="${APP_NAME}-${DEPLOY_STAGE}"
}

check_prereqs() {
  log "Validating prerequisites"

  # The current deploy path needs shell tooling, local packaging, and optionally AgentCore CLI.
  require_cmd aws
  require_cmd python3
  require_cmd zip

  if [[ "${ENABLE_AGENTCORE_DEPLOY}" == "1" ]]; then
    require_cmd agentcore
  fi

  require_file "${PROJECT_ROOT}/tools/gateway_tool_contracts.json"
  require_file "${PROJECT_ROOT}/tools/scoring_weights.json"
  require_file "${PROJECT_ROOT}/data/scenarios.json"
  require_file "${PROJECT_ROOT}/tools/city_context.example.json"
  enforce_deploy_aws_context "deploy"
}

resolve_aws_context() {
  log "Resolving AWS caller context"

  # Dry-run uses a synthetic account ID so later naming stays deterministic without touching AWS.
  if [[ "${DRY_RUN}" == "1" ]]; then
    ACCOUNT_ID="${ACCOUNT_ID:-000000000000}"
    S3_BUCKET="${RESOURCE_PREFIX}-${ACCOUNT_ID}-${AWS_REGION}"
    S3_PREFIX="deploy"
    log "Dry-run mode: using synthetic account=${ACCOUNT_ID} region=${AWS_REGION}"
    return 0
  fi

  ACCOUNT_ID="$("${AWS_CMD[@]}" sts get-caller-identity --query Account --output text)"
  [[ -n "${ACCOUNT_ID}" && "${ACCOUNT_ID}" != "None" ]] || fail "Unable to resolve AWS account ID."

  S3_BUCKET="${RESOURCE_PREFIX}-${ACCOUNT_ID}-${AWS_REGION}"
  S3_PREFIX="deploy"

  log "Using account=${ACCOUNT_ID} region=${AWS_REGION} stage=${DEPLOY_STAGE}"
}

build_deployment_manifest() {
  log "Building deployment manifest at ${MANIFEST_PATH}"

  # The manifest records what this script is expected to manage.
  # It is intentionally small and human-readable so destroy/runbook steps can reuse it.
  PROJECT_ROOT="${PROJECT_ROOT}" \
  MANIFEST_PATH="${MANIFEST_PATH}" \
  APP_NAME="${APP_NAME}" \
  DEPLOY_STAGE="${DEPLOY_STAGE}" \
  AWS_REGION="${AWS_REGION}" \
  ACCOUNT_ID="${ACCOUNT_ID}" \
  RESOURCE_PREFIX="${RESOURCE_PREFIX}" \
  S3_BUCKET="${S3_BUCKET}" \
  AGENTCORE_PROJECT_DIR="${AGENTCORE_PROJECT_DIR}" \
  python3 <<'PY'
import json
import os
from pathlib import Path

manifest_path = Path(os.environ["MANIFEST_PATH"])
manifest_path.parent.mkdir(parents=True, exist_ok=True)

manifest = {
    "app_name": os.environ["APP_NAME"],
    "deploy_stage": os.environ["DEPLOY_STAGE"],
    "aws_region": os.environ["AWS_REGION"],
    "account_id": os.environ["ACCOUNT_ID"],
    "resource_prefix": os.environ["RESOURCE_PREFIX"],
    "s3_bucket": os.environ["S3_BUCKET"],
    "agentcore_project_dir": os.environ["AGENTCORE_PROJECT_DIR"],
    "managed_resources": [
        "s3_bucket",
        "agentcore_runtime",
        "agentcore_gateway",
        "bedrock_model_mapping",
        "cloudwatch_logs",
        "api_gateway_iam_auth",
    ],
}

manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY
}

write_deploy_outputs() {
  log "Writing deploy outputs to ${DEPLOY_OUTPUTS_PATH}"

  # deploy-outputs.json is the machine-readable hand-off used by destroy.sh and later validations.
  DEPLOY_OUTPUTS_PATH="${DEPLOY_OUTPUTS_PATH}" \
  MANIFEST_PATH="${MANIFEST_PATH}" \
  AGENTCORE_STATUS_PATH="${AGENTCORE_STATUS_PATH}" \
  APP_NAME="${APP_NAME}" \
  DEPLOY_STAGE="${DEPLOY_STAGE}" \
  AWS_REGION="${AWS_REGION}" \
  ACCOUNT_ID="${ACCOUNT_ID}" \
  RESOURCE_PREFIX="${RESOURCE_PREFIX}" \
  S3_BUCKET="${S3_BUCKET}" \
  S3_PREFIX="${S3_PREFIX}" \
  AGENTCORE_PROJECT_DIR="${AGENTCORE_PROJECT_DIR}" \
  ENABLE_AGENTCORE_DEPLOY="${ENABLE_AGENTCORE_DEPLOY}" \
  ENABLE_SMOKE_TEST="${ENABLE_SMOKE_TEST}" \
  SMOKE_SCENARIO="${SMOKE_SCENARIO}" \
  SMOKE_ENDPOINT_URL="${SMOKE_ENDPOINT_URL}" \
  python3 <<'PY'
import json
import os
from pathlib import Path

status_path = Path(os.environ["AGENTCORE_STATUS_PATH"])
outputs_path = Path(os.environ["DEPLOY_OUTPUTS_PATH"])
outputs_path.parent.mkdir(parents=True, exist_ok=True)

payload = {
    "app_name": os.environ["APP_NAME"],
    "deploy_stage": os.environ["DEPLOY_STAGE"],
    "aws_region": os.environ["AWS_REGION"],
    "account_id": os.environ["ACCOUNT_ID"],
    "resource_prefix": os.environ["RESOURCE_PREFIX"],
    "s3_bucket": os.environ["S3_BUCKET"],
    "s3_prefix": os.environ["S3_PREFIX"],
    "agentcore_project_dir": os.environ["AGENTCORE_PROJECT_DIR"],
    "manifest_path": os.environ["MANIFEST_PATH"],
    "agentcore_status_path": os.environ["AGENTCORE_STATUS_PATH"],
    "agentcore_status_exists": status_path.exists(),
    "agentcore_deploy_enabled": os.environ["ENABLE_AGENTCORE_DEPLOY"] == "1",
    "smoke_test_enabled": os.environ["ENABLE_SMOKE_TEST"] == "1",
    "smoke_scenario": os.environ["SMOKE_SCENARIO"],
    "smoke_endpoint_url": os.environ["SMOKE_ENDPOINT_URL"] or None,
}

outputs_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

ensure_s3_bucket() {
  log "Ensuring S3 bucket ${S3_BUCKET}"

  # The bucket is the one AWS resource explicitly managed here before AgentCore deploy.
  # It stores packaged artifacts plus deployment evidence needed for reruns and teardown.
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Dry-run mode: assuming bucket does not exist yet"
  elif "${AWS_CMD[@]}" s3api head-bucket --bucket "${S3_BUCKET}" >/dev/null 2>&1; then
    log "S3 bucket already exists: ${S3_BUCKET}"
  else
    if [[ "${AWS_REGION}" == "us-east-1" ]]; then
      run_cmd "${AWS_CMD[@]}" s3api create-bucket \
        --bucket "${S3_BUCKET}"
    else
      run_cmd "${AWS_CMD[@]}" s3api create-bucket \
        --bucket "${S3_BUCKET}" \
        --create-bucket-configuration "LocationConstraint=${AWS_REGION}"
    fi
  fi

  # Even for a POC, the bucket is hardened immediately to avoid carrying weak defaults forward.
  run_cmd "${AWS_CMD[@]}" s3api put-bucket-tagging \
    --bucket "${S3_BUCKET}" \
    --tagging "TagSet=[{Key=project,Value=${APP_NAME}},{Key=stage,Value=${DEPLOY_STAGE}},{Key=owner,Value=${PROJECT_TAG_OWNER}}]"

  run_cmd "${AWS_CMD[@]}" s3api put-public-access-block \
    --bucket "${S3_BUCKET}" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

  run_cmd "${AWS_CMD[@]}" s3api put-bucket-encryption \
    --bucket "${S3_BUCKET}" \
    --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

  run_cmd "${AWS_CMD[@]}" s3api put-bucket-ownership-controls \
    --bucket "${S3_BUCKET}" \
    --ownership-controls '{"Rules":[{"ObjectOwnership":"BucketOwnerEnforced"}]}'

  run_cmd "${AWS_CMD[@]}" s3api put-bucket-versioning \
    --bucket "${S3_BUCKET}" \
    --versioning-configuration "Status=Enabled"
}

prepare_artifacts() {
  log "Preparing deployment artifacts"

  # The package contains only the deterministic inputs/config that the target runtime needs to replay.
  rm -rf "${ARTIFACTS_DIR}"
  mkdir -p "${ARTIFACTS_DIR}/tools" "${ARTIFACTS_DIR}/data"

  cp "${PROJECT_ROOT}/tools/gateway_tool_contracts.json" "${ARTIFACTS_DIR}/tools/"
  cp "${PROJECT_ROOT}/tools/scoring_weights.json" "${ARTIFACTS_DIR}/tools/"
  cp "${PROJECT_ROOT}/tools/city_context.example.json" "${ARTIFACTS_DIR}/tools/"
  cp "${PROJECT_ROOT}/data/scenarios.json" "${ARTIFACTS_DIR}/data/"

  (
    cd "${ARTIFACTS_DIR}"
    run_cmd zip -rq "${OUTPUT_DIR}/deploy-artifacts.zip" .
  )

  run_cmd "${AWS_CMD[@]}" s3 cp \
    "${OUTPUT_DIR}/deploy-artifacts.zip" \
    "s3://${S3_BUCKET}/${S3_PREFIX}/deploy-artifacts.zip"

  run_cmd "${AWS_CMD[@]}" s3 cp \
    "${MANIFEST_PATH}" \
    "s3://${S3_BUCKET}/${S3_PREFIX}/deployment-manifest.json"
}

validate_agentcore_project() {
  [[ "${ENABLE_AGENTCORE_DEPLOY}" == "1" ]] || return 0

  log "Validating AgentCore project layout"

  # We validate the target project before deeper deploy steps so configuration problems fail early.
  require_dir "${AGENTCORE_PROJECT_DIR}"
  require_dir "${AGENTCORE_CONFIG_DIR}"
  require_file "${AGENTCORE_CONFIG_DIR}/agentcore.json"
  require_file "${AGENTCORE_CONFIG_DIR}/aws-targets.json"

  log "AgentCore project dir=${AGENTCORE_PROJECT_DIR}"

  AGENTCORE_TARGET_COUNT="$(
    python3 - "${AGENTCORE_CONFIG_DIR}/aws-targets.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(len(payload))
PY
  )"

if [[ "${AGENTCORE_TARGET_COUNT}" == "0" ]]; then
    warn "No AgentCore deployment targets configured in ${AGENTCORE_CONFIG_DIR}/aws-targets.json"
    warn "Skipping live AgentCore deployment. Fill deployment targets, then rerun deploy.sh."
    # Missing targets is treated as a controlled skip, not as a hard failure, to keep the script
    # usable before the first real account/region binding exists.
    ENABLE_AGENTCORE_DEPLOY="0"
    return 0
  fi

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Dry-run mode: AgentCore validation command not executed"
    return 0
  fi

  (
    cd "${AGENTCORE_PROJECT_DIR}"
    agentcore validate
  )
}

ensure_foundations() {
  log "Preparing AWS foundations"
  # IAM roles, API Gateway auth, and runtime resources are expected to come from AgentCore/CDK.
  # This script only prepares the shared prerequisites around that deployment.
  log "IAM, API Gateway auth, and runtime roles are expected to be synthesized by the AgentCore project deployment."
  log "This script ensures the shared artifact bucket and deploy manifest before delegating runtime creation."
}

deploy_agentcore_runtime() {
  [[ "${ENABLE_AGENTCORE_DEPLOY}" == "1" ]] || {
    warn "AgentCore deployment skipped"
    return 0
  }

  log "Deploying AgentCore runtime and gateway"

  # The actual runtime deployment is delegated to the AgentCore CLI once local preconditions are met.
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Dry-run mode: would run 'agentcore deploy --target ${AGENTCORE_TARGET_NAME} --yes' and 'agentcore status --target ${AGENTCORE_TARGET_NAME} --json' in ${AGENTCORE_PROJECT_DIR}"
    return 0
  fi

  (
    cd "${AGENTCORE_PROJECT_DIR}"
    agentcore deploy --target "${AGENTCORE_TARGET_NAME}" --yes
    agentcore status --target "${AGENTCORE_TARGET_NAME}" --json | tee "${AGENTCORE_STATUS_PATH}"
  )
}

wire_observability() {
  # Observability is noted explicitly here because it is part of the target story,
  # even though the concrete resources are currently synthesized by AgentCore/CDK.
  log "Observability wiring is delegated to AgentCore/CDK deployment."
  log "Expected outputs: CloudWatch log groups, stage logging, and runtime traces."
}

print_manual_smoke_instructions() {
  [[ "${ENABLE_SMOKE_TEST}" == "1" ]] || {
    log "Manual smoke instructions disabled"
    return 0
  }

  log "Preparing manual smoke instructions"

  if [[ -z "${SMOKE_ENDPOINT_URL}" ]]; then
    warn "ENABLE_SMOKE_TEST=1 but SMOKE_ENDPOINT_URL is empty. No manual smoke instructions emitted."
    return 0
  fi

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Dry-run mode: would print SigV4 smoke instructions for ${SMOKE_ENDPOINT_URL} and scenario ${SMOKE_SCENARIO}"
    return 0
  fi

  cat <<EOF
[deploy][warn] Manual smoke validation is still required because the final signed request shape is not frozen.
[deploy][warn] Target endpoint: ${SMOKE_ENDPOINT_URL}
[deploy][warn] Scenario to replay: ${SMOKE_SCENARIO}
[deploy][warn] Expected next step: invoke the endpoint with AWS_IAM / SigV4 and verify the JSON response shape.
EOF
}

print_summary() {
  log "Deployment summary"
  cat <<EOF
Manifest: ${MANIFEST_PATH}
Deploy outputs: ${DEPLOY_OUTPUTS_PATH}
Artifacts zip: ${OUTPUT_DIR}/deploy-artifacts.zip
S3 bucket: ${S3_BUCKET}
S3 manifest: s3://${S3_BUCKET}/${S3_PREFIX}/deployment-manifest.json
AgentCore project dir: ${AGENTCORE_PROJECT_DIR}
AgentCore status output: ${AGENTCORE_STATUS_PATH}
AgentCore deploy enabled: ${ENABLE_AGENTCORE_DEPLOY}
AgentCore target name: ${AGENTCORE_TARGET_NAME}
Smoke test enabled: ${ENABLE_SMOKE_TEST}
Expected AWS account: ${EXPECTED_AWS_ACCOUNT_ID:-<unset>}
EOF

  if [[ "${ENABLE_AGENTCORE_DEPLOY}" == "0" ]]; then
    warn "AgentCore deployment was skipped. Configure ${AGENTCORE_CONFIG_DIR}/aws-targets.json before rerunning."
  fi
}

main() {
  # Order matters:
  # 1. resolve config and caller context
  # 2. fail early on AgentCore structure
  # 3. prepare deploy evidence and shared bucket
  # 4. delegate runtime creation
  # 5. persist outputs for smoke/teardown
  load_config
  check_prereqs
  resolve_aws_context
  validate_agentcore_project
  build_deployment_manifest
  ensure_s3_bucket
  prepare_artifacts
  ensure_foundations
  deploy_agentcore_runtime
  wire_observability
  write_deploy_outputs
  print_manual_smoke_instructions
  print_summary
}

main "$@"
