variable "region" {
  description = "AWS region for the service and its Bedrock calls."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Name of the Lambda function, role and table prefix."
  type        = string
  default     = "depfix-llm-proxy"
}

variable "repo_daily_tokens" {
  description = "Tokens one repository may use per UTC day."
  type        = number
  default     = 1000000
}

variable "global_daily_tokens" {
  description = "Tokens all repositories together may use per UTC day."
  type        = number
  default     = 5000000
}

variable "max_concurrency" {
  description = "Most requests served at once; -1 leaves it to the account's Lambda limit (AWS needs 10 unreserved, so small accounts can't reserve)."
  type        = number
  default     = -1
}
