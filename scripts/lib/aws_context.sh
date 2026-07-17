#!/usr/bin/env bash

AWS_CONTEXT_REPO_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
AWS_CONTEXT_FILE_DEFAULT="${AWS_CONTEXT_REPO_ROOT}/.env.deploy.local"

aws_context_log() {
  local caller="${1:-aws-context}"
  shift || true
  printf '[%s] %s\n' "${caller}" "$*"
}

aws_context_warn() {
  local caller="${1:-aws-context}"
  shift || true
  printf '[%s][warn] %s\n' "${caller}" "$*" >&2
}

aws_context_fail() {
  local caller="${1:-aws-context}"
  shift || true
  printf '[%s][error] %s\n' "${caller}" "$*" >&2
  exit 1
}

load_deploy_aws_context() {
  local caller="${1:-aws-context}"
  local context_file="${AWS_CONTEXT_FILE:-${AWS_CONTEXT_FILE_DEFAULT}}"

  if [[ -f "${context_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${context_file}"
    set +a
    aws_context_log "${caller}" "Loaded local AWS context from ${context_file}"
  else
    aws_context_warn "${caller}" "Local AWS context file not found at ${context_file}"
  fi

  if [[ -n "${REQUIRED_AWS_PROFILE:-}" && -z "${AWS_PROFILE:-}" ]]; then
    export AWS_PROFILE="${REQUIRED_AWS_PROFILE}"
  fi

  if [[ -n "${EXPECTED_AWS_REGION:-}" && -z "${AWS_REGION:-}" && -z "${AWS_DEFAULT_REGION:-}" ]]; then
    export AWS_REGION="${EXPECTED_AWS_REGION}"
  fi
}

enforce_deploy_aws_context() {
  local caller="${1:-aws-context}"
  local strict="${STRICT_AWS_CONTEXT:-1}"
  local aws_cmd=(aws)
  local actual_account=""

  if [[ "${strict}" != "1" ]]; then
    aws_context_warn "${caller}" "STRICT_AWS_CONTEXT=${strict}; AWS context enforcement disabled"
    return 0
  fi

  [[ -n "${REQUIRED_AWS_PROFILE:-}" ]] || aws_context_fail "${caller}" "REQUIRED_AWS_PROFILE must be set."
  [[ -n "${EXPECTED_AWS_ACCOUNT_ID:-}" ]] || aws_context_fail "${caller}" "EXPECTED_AWS_ACCOUNT_ID must be set."
  [[ -n "${AWS_PROFILE:-}" ]] || aws_context_fail "${caller}" "AWS_PROFILE is empty."

  if [[ "${AWS_PROFILE}" != "${REQUIRED_AWS_PROFILE}" ]]; then
    aws_context_fail "${caller}" \
      "AWS_PROFILE=${AWS_PROFILE} does not match required profile ${REQUIRED_AWS_PROFILE}."
  fi

  if [[ -n "${EXPECTED_AWS_REGION:-}" ]]; then
    local current_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
    [[ -n "${current_region}" ]] || aws_context_fail "${caller}" "AWS region is empty."
    if [[ "${current_region}" != "${EXPECTED_AWS_REGION}" ]]; then
      aws_context_fail "${caller}" \
        "AWS region ${current_region} does not match expected region ${EXPECTED_AWS_REGION}."
    fi
  fi

  aws_cmd+=(--profile "${AWS_PROFILE}")
  if [[ -n "${AWS_REGION:-${AWS_DEFAULT_REGION:-}}" ]]; then
    aws_cmd+=(--region "${AWS_REGION:-${AWS_DEFAULT_REGION:-}}")
  fi

  actual_account="$("${aws_cmd[@]}" sts get-caller-identity --query Account --output text 2>/dev/null)" || \
    aws_context_fail "${caller}" "Unable to resolve AWS account for profile ${AWS_PROFILE}."

  if [[ "${actual_account}" != "${EXPECTED_AWS_ACCOUNT_ID}" ]]; then
    aws_context_fail "${caller}" \
      "Resolved AWS account ${actual_account} does not match expected account ${EXPECTED_AWS_ACCOUNT_ID}."
  fi

  aws_context_log "${caller}" \
    "AWS context locked to profile=${AWS_PROFILE} account=${actual_account} region=${AWS_REGION:-${AWS_DEFAULT_REGION:-<unset>}}"
}
