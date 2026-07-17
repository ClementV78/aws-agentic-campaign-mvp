#!/usr/bin/env bash
# Configure the AWS CLI profile/region for this project's AgentCore target.
# This must be SOURCED, not executed, so the exports affect your current shell:
#   source scripts/aws_env.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/lib/aws_context.sh"
load_deploy_aws_context "aws_env"
enforce_deploy_aws_context "aws_env"

echo "AWS_PROFILE=${AWS_PROFILE}"
echo "AWS_REGION=${AWS_REGION}"
echo "EXPECTED_AWS_ACCOUNT_ID=${EXPECTED_AWS_ACCOUNT_ID}"

if aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials OK ($(aws --profile "${AWS_PROFILE}" --region "${AWS_REGION}" sts get-caller-identity --query Account --output text))"
else
  echo "Warning: could not verify AWS credentials for profile ${AWS_PROFILE}"
fi
