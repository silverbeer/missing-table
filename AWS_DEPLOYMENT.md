# AWS Deployment Guide

This guide covers deploying the Sports League Management application to AWS with production-ready infrastructure.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CloudFront    │────▶│   S3 Bucket     │     │   Route 53      │
│   (CDN)         │     │   (Frontend)    │     │   (DNS)         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ALB           │────▶│   ECS Fargate   │────▶│   ElastiCache   │
│   (Load Balancer)│     │   (Backend)     │     │   (Redis)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Supabase      │
                        │   (Database)    │
                        └─────────────────┘
```

## Prerequisites

1. AWS Account with appropriate permissions
2. AWS CLI installed and configured
3. Docker installed locally
4. Domain name (optional but recommended)

## 1. Infrastructure Setup

### 1.1 Create VPC and Networking

Create a `terraform/network.tf` file:

```hcl
# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "sports-league-vpc"
  }
}

# Public Subnets (for ALB)
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "sports-league-public-${count.index + 1}"
  }
}

# Private Subnets (for ECS)
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "sports-league-private-${count.index + 1}"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "sports-league-igw"
  }
}

# NAT Gateway
resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"

  tags = {
    Name = "sports-league-nat-${count.index + 1}"
  }
}

resource "aws_nat_gateway" "main" {
  count         = 2
  subnet_id     = aws_subnet.public[count.index].id
  allocation_id = aws_eip.nat[count.index].id

  tags = {
    Name = "sports-league-nat-${count.index + 1}"
  }
}
```

### 1.2 Backend Infrastructure (ECS Fargate)

Create `terraform/ecs.tf`:

```hcl
# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "sports-league-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "sports-league-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "backend"
      image = "${aws_ecr_repository.backend.repository_url}:latest"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379"
        },
        {
          name  = "USE_REDIS_RATE_LIMIT"
          value = "true"
        }
      ]

      secrets = [
        {
          name      = "SUPABASE_URL"
          valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SUPABASE_URL::"
        },
        {
          name      = "SUPABASE_ANON_KEY"
          valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SUPABASE_ANON_KEY::"
        },
        {
          name      = "SUPABASE_SERVICE_KEY"
          valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SUPABASE_SERVICE_KEY::"
        },
        {
          name      = "SUPABASE_JWT_SECRET"
          valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SUPABASE_JWT_SECRET::"
        },
        {
          name      = "CSRF_SECRET_KEY"
          valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:CSRF_SECRET_KEY::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/sports-league-backend"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "backend" {
  name            = "sports-league-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.backend]
}

# Auto Scaling
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_cpu" {
  name               = "sports-league-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

### 1.3 Frontend Infrastructure (S3 + CloudFront)

Create `terraform/frontend.tf`:

```hcl
# S3 Bucket for Frontend
resource "aws_s3_bucket" "frontend" {
  bucket = "sports-league-frontend-${var.environment}"
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "frontend" {
  origin {
    domain_name = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.frontend.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.frontend.cloudfront_access_identity_path
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  aliases = [var.domain_name]

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.frontend.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 31536000
  }

  # API pass-through
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "ALB-${aws_lb.main.id}"

    forwarded_values {
      query_string = true
      headers      = ["*"]
      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "https-only"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }

  price_class = "PriceClass_100"

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn = aws_acm_certificate.main.arn
    ssl_support_method  = "sni-only"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }
}
```

### 1.4 Redis (ElastiCache)

Create `terraform/redis.tf`:

```hcl
# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "redis" {
  name       = "sports-league-redis"
  subnet_ids = aws_subnet.private[*].id
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "sports-league-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = {
    Name = "sports-league-redis"
  }
}
```

## 2. Security Configuration

### 2.1 Secrets Manager

Create `terraform/secrets.tf`:

```hcl
# Secrets Manager
resource "aws_secretsmanager_secret" "app_secrets" {
  name = "sports-league-app-secrets"
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    SUPABASE_URL         = var.supabase_url
    SUPABASE_ANON_KEY    = var.supabase_anon_key
    SUPABASE_SERVICE_KEY = var.supabase_service_key
    SUPABASE_JWT_SECRET  = var.supabase_jwt_secret
    CSRF_SECRET_KEY      = random_password.csrf_key.result
  })
}

resource "random_password" "csrf_key" {
  length  = 32
  special = true
}
```

### 2.2 Security Groups

Create `terraform/security.tf`:

```hcl
# ALB Security Group
resource "aws_security_group" "alb" {
  name        = "sports-league-alb"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ECS Security Group
resource "aws_security_group" "ecs" {
  name        = "sports-league-ecs"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Redis Security Group
resource "aws_security_group" "redis" {
  name        = "sports-league-redis"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

## 3. CI/CD Pipeline

### 3.1 GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main, production]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: sports-league-backend

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install uv
          uv pip install -e ".[dev]"
      
      - name: Run tests
        run: |
          cd backend
          pytest

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/production'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-get-login@v1
      
      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd backend
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
      
      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster sports-league-cluster \
            --service sports-league-backend \
            --force-new-deployment

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/production'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install and build
        run: |
          cd frontend
          npm ci
          npm run build
        env:
          VUE_APP_API_URL: https://api.yourdomain.com
          VUE_APP_SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          VUE_APP_SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
      
      - name: Deploy to S3
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Sync S3 bucket
        run: |
          aws s3 sync frontend/dist/ s3://sports-league-frontend-production \
            --delete \
            --cache-control "public, max-age=31536000" \
            --exclude "index.html" \
            --exclude "*.json"
          
          aws s3 cp frontend/dist/index.html s3://sports-league-frontend-production/index.html \
            --cache-control "no-cache, no-store, must-revalidate"
      
      - name: Invalidate CloudFront
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CLOUDFRONT_DISTRIBUTION_ID }} \
            --paths "/*"
```

### 3.2 Backend Dockerfile

Update `backend/Dockerfile`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install uv && uv pip install -e .

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run the application
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 4. Monitoring and Logging

### 4.1 CloudWatch Configuration

Create `terraform/monitoring.tf`:

```hcl
# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/sports-league-backend"
  retention_in_days = 7
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "sports-league-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors ECS CPU utilization"

  dimensions = {
    ServiceName = aws_ecs_service.backend.name
    ClusterName = aws_ecs_cluster.main.name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy" {
  alarm_name          = "sports-league-unhealthy-hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "Alert when we have unhealthy hosts"

  dimensions = {
    TargetGroup  = aws_lb_target_group.backend.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name = "sports-league-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

### 4.2 Application Monitoring

Add health check endpoint to `backend/app.py`:

```python
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer."""
    try:
        # Check database connection
        db_conn_holder_obj.client.table('teams').select('id').limit(1).execute()
        
        # Check Redis if enabled
        if USE_REDIS and redis_client:
            redis_client.ping()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
```

## 5. Cost Optimization

### 5.1 Cost Estimation (Monthly)

- **ECS Fargate** (2 tasks, 0.5 vCPU, 1GB): ~$40
- **Application Load Balancer**: ~$25
- **ElastiCache Redis** (t3.micro): ~$15
- **CloudFront**: ~$10 (varies with traffic)
- **S3**: ~$5
- **Route 53**: ~$1
- **Total**: ~$96/month + data transfer

### 5.2 Cost Optimization Tips

1. **Use Spot Instances** for non-critical workloads
2. **Enable S3 Lifecycle Policies** for logs
3. **Use CloudFront caching** aggressively
4. **Schedule ECS tasks** to scale down during off-hours
5. **Use Reserved Instances** for predictable workloads

## 6. Deployment Steps

1. **Prepare AWS Account**:
   ```bash
   # Create S3 bucket for Terraform state
   aws s3 mb s3://sports-league-terraform-state
   
   # Create ECR repository
   aws ecr create-repository --repository-name sports-league-backend
   ```

2. **Configure Terraform**:
   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```

3. **Deploy Application**:
   ```bash
   # Build and push Docker image
   cd backend
   docker build -t sports-league-backend .
   docker tag sports-league-backend:latest $ECR_URL:latest
   docker push $ECR_URL:latest
   
   # Deploy frontend
   cd ../frontend
   npm run build
   aws s3 sync dist/ s3://sports-league-frontend-production
   ```

4. **Configure DNS**:
   - Point your domain to CloudFront distribution
   - Update SSL certificate in ACM

5. **Test Deployment**:
   ```bash
   # Test API
   curl https://api.yourdomain.com/health
   
   # Test Frontend
   curl https://yourdomain.com
   ```

## 7. Disaster Recovery

### 7.1 Backup Strategy

1. **Database**: Supabase handles backups automatically
2. **Application State**: Stateless design, no backup needed
3. **Infrastructure**: Terraform state in S3 with versioning
4. **Secrets**: AWS Secrets Manager with automatic rotation

### 7.2 Recovery Procedures

1. **Service Failure**: ECS automatically restarts failed tasks
2. **AZ Failure**: Multi-AZ deployment ensures availability
3. **Region Failure**: Use Route 53 health checks for failover
4. **Data Loss**: Restore from Supabase backups

## 8. Security Checklist

- [ ] Enable AWS WAF on CloudFront
- [ ] Configure AWS Shield for DDoS protection
- [ ] Enable VPC Flow Logs
- [ ] Set up AWS GuardDuty
- [ ] Configure AWS Config rules
- [ ] Enable CloudTrail logging
- [ ] Implement least privilege IAM policies
- [ ] Enable MFA for AWS accounts
- [ ] Encrypt data at rest and in transit
- [ ] Regular security audits with AWS Security Hub

## Support

For deployment issues:
1. Check CloudWatch logs
2. Verify security group rules
3. Check ECS task definitions
4. Validate environment variables
5. Test connectivity between services