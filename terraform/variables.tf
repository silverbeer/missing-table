# Terraform Variables for Sports League App

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "yourdomain.com"
}

variable "api_subdomain" {
  description = "Subdomain for API"
  type        = string
  default     = "api"
}

variable "alert_email" {
  description = "Email address for alerts"
  type        = string
}

# Supabase Configuration
variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
  sensitive   = true
}

variable "supabase_anon_key" {
  description = "Supabase anonymous key"
  type        = string
  sensitive   = true
}

variable "supabase_service_key" {
  description = "Supabase service role key"
  type        = string
  sensitive   = true
}

variable "supabase_jwt_secret" {
  description = "Supabase JWT secret"
  type        = string
  sensitive   = true
}

# Application Configuration
variable "app_name" {
  description = "Application name"
  type        = string
  default     = "sports-league"
}

variable "app_version" {
  description = "Application version"
  type        = string
  default     = "2.0.0"
}

# Infrastructure Configuration
variable "backend_cpu" {
  description = "CPU units for backend container"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Memory for backend container (MB)"
  type        = number
  default     = 1024
}

variable "backend_min_capacity" {
  description = "Minimum number of backend tasks"
  type        = number
  default     = 2
}

variable "backend_max_capacity" {
  description = "Maximum number of backend tasks"
  type        = number
  default     = 10
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "enable_redis" {
  description = "Enable Redis for rate limiting"
  type        = bool
  default     = true
}

# Security Configuration
variable "enable_waf" {
  description = "Enable AWS WAF"
  type        = bool
  default     = true
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access the application"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# Monitoring Configuration
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "enable_detailed_monitoring" {
  description = "Enable detailed CloudWatch monitoring"
  type        = bool
  default     = true
}

# Cost Optimization
variable "enable_spot_instances" {
  description = "Use Spot instances for ECS (development only)"
  type        = bool
  default     = false
}

# Tags
variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "SportsLeague"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}