#!/usr/bin/env bash
# Deploy (or update) the depfix hosted LLM service: one Lambda with a public
# function URL, one DynamoDB table for daily usage, one IAM role. Idempotent.
#
#   AWS_PROFILE=Bedil bash proxy/deploy.sh
set -euo pipefail

REGION="${REGION:-us-east-1}"
NAME="${NAME:-depfix-llm-proxy}"
TABLE="${TABLE:-depfix-proxy-usage}"
REPO_DAILY_TOKENS="${REPO_DAILY_TOKENS:-1000000}"
GLOBAL_DAILY_TOKENS="${GLOBAL_DAILY_TOKENS:-5000000}"
CONCURRENCY="${CONCURRENCY:-5}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
aws() { command aws --region "$REGION" "$@"; }

if ! aws dynamodb describe-table --table-name "$TABLE" >/dev/null 2>&1; then
  aws dynamodb create-table --table-name "$TABLE" \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --table-name "$TABLE"
  aws dynamodb update-time-to-live --table-name "$TABLE" \
    --time-to-live-specification Enabled=true,AttributeName=expires_at >/dev/null
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${NAME}"
if ! aws iam get-role --role-name "$NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$NAME" --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]
  }' >/dev/null
  aws iam attach-role-policy --role-name "$NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  sleep 10  # IAM propagation before Lambda can assume the role
fi
aws iam put-role-policy --role-name "$NAME" --policy-name "$NAME" --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {\"Effect\": \"Allow\", \"Action\": \"bedrock:InvokeModel\",
     \"Resource\": [\"arn:aws:bedrock:*::foundation-model/anthropic.*\",
                    \"arn:aws:bedrock:*:${ACCOUNT}:inference-profile/us.anthropic.*\"]},
    {\"Effect\": \"Allow\", \"Action\": [\"dynamodb:GetItem\", \"dynamodb:UpdateItem\"],
     \"Resource\": \"arn:aws:dynamodb:${REGION}:${ACCOUNT}:table/${TABLE}\"}
  ]
}"

ZIP="$(mktemp -d)/handler.zip"
(cd "$HERE" && zip -q "$ZIP" handler.py)
ENV="Variables={USAGE_TABLE=${TABLE},BEDROCK_REGION=${REGION},REPO_DAILY_TOKENS=${REPO_DAILY_TOKENS},GLOBAL_DAILY_TOKENS=${GLOBAL_DAILY_TOKENS}}"

if aws lambda get-function --function-name "$NAME" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$NAME" --zip-file "fileb://$ZIP" >/dev/null
  aws lambda wait function-updated --function-name "$NAME"
  aws lambda update-function-configuration --function-name "$NAME" --environment "$ENV" >/dev/null
else
  aws lambda create-function --function-name "$NAME" --runtime python3.13 \
    --handler handler.lambda_handler --role "$ROLE_ARN" --zip-file "fileb://$ZIP" \
    --timeout 300 --memory-size 256 --environment "$ENV" >/dev/null
  aws lambda wait function-active --function-name "$NAME"
fi
aws lambda put-function-concurrency --function-name "$NAME" \
  --reserved-concurrent-executions "$CONCURRENCY" >/dev/null

if ! aws lambda get-function-url-config --function-name "$NAME" >/dev/null 2>&1; then
  aws lambda create-function-url-config --function-name "$NAME" --auth-type NONE >/dev/null
  aws lambda add-permission --function-name "$NAME" --statement-id public-url \
    --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE >/dev/null
fi
aws lambda get-function-url-config --function-name "$NAME" --query FunctionUrl --output text
