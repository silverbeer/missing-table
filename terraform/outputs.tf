# Terraform Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Application Load Balancer Zone ID"
  value       = aws_lb.main.zone_id
}

output "cloudfront_distribution_id" {
  description = "CloudFront Distribution ID"
  value       = aws_cloudfront_distribution.frontend.id
}

output "cloudfront_domain_name" {
  description = "CloudFront Domain Name"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "s3_bucket_name" {
  description = "S3 bucket name for frontend"
  value       = aws_s3_bucket.frontend.bucket
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.backend.name
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = var.enable_redis ? aws_elasticache_cluster.redis[0].cache_nodes[0].address : null
}

output "redis_port" {
  description = "Redis port"
  value       = var.enable_redis ? aws_elasticache_cluster.redis[0].cache_nodes[0].port : null
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "https://${var.api_subdomain}.${var.domain_name}"
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "https://${var.domain_name}"
}

output "secrets_manager_arn" {
  description = "Secrets Manager ARN"
  value       = aws_secretsmanager_secret.app_secrets.arn
}

output "deployment_commands" {
  description = "Commands to deploy the application"
  value = {
    docker_login = "aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.backend.repository_url}"
    docker_build = "docker build -t ${local.name_prefix}-backend backend/"
    docker_tag   = "docker tag ${local.name_prefix}-backend:latest ${aws_ecr_repository.backend.repository_url}:latest"
    docker_push  = "docker push ${aws_ecr_repository.backend.repository_url}:latest"
    ecs_update   = "aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service ${aws_ecs_service.backend.name} --force-new-deployment"
    s3_sync      = "aws s3 sync frontend/dist/ s3://${aws_s3_bucket.frontend.bucket}/"
    cf_invalidate = "aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.frontend.id} --paths '/*'"
  }
}