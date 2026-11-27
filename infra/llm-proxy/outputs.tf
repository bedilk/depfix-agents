output "service_url" {
  description = "Set this as the Action's llm-service-url default."
  value       = aws_lambda_function_url.proxy.function_url
}
