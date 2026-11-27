# depfix hosted LLM service: one Lambda with a public function URL, a DynamoDB
# table of daily token counts, and a role that can only call Claude on Bedrock
# and that table. The account is read from the caller's AWS credentials; no
# account ID, key or secret lives in this code.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account   = data.aws_caller_identity.current.account_id
  partition = data.aws_partition.current.partition
}

resource "aws_dynamodb_table" "usage" {
  name         = "${var.name}-usage"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

resource "aws_iam_role" "proxy" {
  name = var.name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.proxy.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "proxy" {
  name = var.name
  role = aws_iam_role.proxy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "bedrock:InvokeModel"
        Resource = [
          "arn:${local.partition}:bedrock:*::foundation-model/anthropic.*",
          "arn:${local.partition}:bedrock:*:${local.account}:inference-profile/us.anthropic.*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.usage.arn
      },
    ]
  })
}

data "archive_file" "handler" {
  type        = "zip"
  source_file = "${path.module}/../../proxy/handler.py"
  output_path = "${path.module}/.build/handler.zip"
}

resource "aws_cloudwatch_log_group" "proxy" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "proxy" {
  function_name                  = var.name
  role                           = aws_iam_role.proxy.arn
  runtime                        = "python3.13"
  handler                        = "handler.lambda_handler"
  filename                       = data.archive_file.handler.output_path
  source_code_hash               = data.archive_file.handler.output_base64sha256
  timeout                        = 300
  memory_size                    = 256
  reserved_concurrent_executions = var.max_concurrency

  environment {
    variables = {
      USAGE_TABLE         = aws_dynamodb_table.usage.name
      BEDROCK_REGION      = var.region
      REPO_DAILY_TOKENS   = tostring(var.repo_daily_tokens)
      GLOBAL_DAILY_TOKENS = tostring(var.global_daily_tokens)
    }
  }

  depends_on = [aws_cloudwatch_log_group.proxy, aws_iam_role_policy_attachment.logs]
}

resource "aws_lambda_function_url" "proxy" {
  function_name      = aws_lambda_function.proxy.function_name
  authorization_type = "NONE"
}

# A public URL still needs resource-based permission for anonymous callers;
# the handler itself rejects anything without a valid GitHub Actions token.
resource "aws_lambda_permission" "url" {
  statement_id           = "public-function-url"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.proxy.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invoke" {
  statement_id             = "public-function-url-invoke"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.proxy.function_name
  principal                = "*"
  invoked_via_function_url = true
}
