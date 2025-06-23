# Scintilla Terraform Outputs
# Expose important resource information for external use

# Network Information
output "vpc_id" {
  description = "ID of the existing VPC being used"
  value       = data.aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the existing VPC"
  value       = data.aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the existing public subnets being used"
  value       = data.aws_subnets.public.ids
}

output "private_subnet_ids" {
  description = "IDs of the existing private subnets being used"
  value       = data.aws_subnets.private.ids
}

output "database_subnet_ids" {
  description = "IDs of the existing database subnets being used"
  value       = data.aws_subnets.database.ids
}

output "internet_gateway_id" {
  description = "ID of the existing internet gateway"
  value       = data.aws_internet_gateway.main.id
}

# Load Balancer Information
output "load_balancer_dns" {
  description = "DNS name of the application load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_zone_id" {
  description = "Zone ID of the application load balancer"
  value       = aws_lb.main.zone_id
}

output "load_balancer_arn" {
  description = "ARN of the load balancer"
  value       = aws_lb.main.arn
}

output "target_group_arn" {
  description = "ARN of the target group"
  value       = aws_lb_target_group.app.arn
}

# Application URL
output "application_url" {
  description = "URL of the application load balancer"
  value       = "http://${aws_lb.main.dns_name}"
}

# Database Information
output "database_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.address
  sensitive   = true
}

output "database_port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "database_name" {
  description = "Database name"
  value       = aws_db_instance.main.db_name
}

output "database_username" {
  description = "Database username"
  value       = aws_db_instance.main.username
  sensitive   = true
}

# Security Group Information
output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = aws_security_group.alb.id
}

output "app_security_group_id" {
  description = "ID of the application security group"
  value       = aws_security_group.app.id
}

output "database_security_group_id" {
  description = "ID of the database security group"
  value       = aws_security_group.database.id
}

# Auto Scaling Information
output "autoscaling_group_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.app.name
}

output "autoscaling_group_arn" {
  description = "ARN of the Auto Scaling Group"
  value       = aws_autoscaling_group.app.arn
}

output "launch_configuration_name" {
  description = "Name of the launch configuration"
  value       = aws_launch_configuration.app.name
}

# IAM Information
output "app_instance_profile_name" {
  description = "Name of the application instance profile"
  value       = aws_iam_instance_profile.app.name
}

output "app_role_arn" {
  description = "ARN of the application IAM role"
  value       = aws_iam_role.app.arn
}

# KMS Information
output "kms_key_id" {
  description = "ID of the KMS key"
  value       = aws_kms_key.main.key_id
  sensitive   = true
}

output "kms_key_arn" {
  description = "ARN of the KMS key"
  value       = aws_kms_key.main.arn
  sensitive   = true
}

output "kms_alias_name" {
  description = "Name of the KMS key alias"
  value       = aws_kms_alias.main.name
}

# CloudWatch Information
output "app_log_group_name" {
  description = "Name of the application log group"
  value       = aws_cloudwatch_log_group.app.name
}

output "access_log_group_name" {
  description = "Name of the access log group"
  value       = aws_cloudwatch_log_group.access.name
}

# Environment Information
output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "project_name" {
  description = "Project name"
  value       = var.project_name
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

# Connection Information for Applications
output "connection_info" {
  description = "Information needed to connect to the deployed resources"
  value = {
    application_url        = "http://${aws_lb.main.dns_name}"
    load_balancer_dns     = aws_lb.main.dns_name
    database_endpoint     = aws_db_instance.main.address
    database_port         = aws_db_instance.main.port
    database_name         = aws_db_instance.main.db_name
    kms_key_alias         = aws_kms_alias.main.name
  }
  sensitive = true
}

# Deployment Information
output "deployment_summary" {
  description = "Summary of the deployment configuration"
  value = {
    project_name     = var.project_name
    environment      = var.environment
    aws_region       = var.aws_region
    existing_vpc_id  = var.existing_vpc_id
    instance_type    = var.instance_type
    db_instance_class = var.db_instance_class
    min_capacity     = var.asg_min_size
    max_capacity     = var.asg_max_size
    desired_capacity = var.asg_desired_capacity
  }
}

# Monitoring Information
output "monitoring_info" {
  description = "CloudWatch monitoring resources"
  value = {
    app_log_group    = aws_cloudwatch_log_group.app.name
    access_log_group = aws_cloudwatch_log_group.access.name
    log_retention    = var.log_retention_days
  }
}

# Infrastructure Status
output "infrastructure_status" {
  description = "Status of infrastructure components"
  value = {
    vpc_type = "existing"
    vpc_id   = data.aws_vpc.main.id
    public_subnets_count  = length(data.aws_subnets.public.ids)
    private_subnets_count = length(data.aws_subnets.private.ids)
    database_subnets_count = length(data.aws_subnets.database.ids)
    security_groups_created = 3
    kms_encryption_enabled = true
  }
}

# Cost Estimation Information
output "estimated_costs" {
  description = "Estimated monthly costs by service (USD)"
  value = {
    ec2_instances = {
      instance_type    = var.instance_type
      min_instances    = var.asg_min_size
      max_instances    = var.asg_max_size
      estimated_cost   = var.environment == "development" ? "$15-30" : var.environment == "staging" ? "$50-100" : "$150-300"
    }
    rds_database = {
      instance_class = var.db_instance_class
      storage_gb     = var.db_allocated_storage
      multi_az       = var.environment == "production" ? "Yes" : "No"
      estimated_cost = var.environment == "development" ? "$15-25" : var.environment == "staging" ? "$30-50" : "$200-400"
    }
    load_balancer = {
      type           = "Application Load Balancer"
      estimated_cost = "$16-20"
    }
    cloudwatch = {
      log_retention_days = var.log_retention_days
      estimated_cost     = "$5-15"
    }
    total_estimated_range = var.environment == "development" ? "$50-100" : var.environment == "staging" ? "$150-250" : "$500-1000"
  }
}

# SSH Access Information (if key pair is configured)
output "ssh_access_info" {
  description = "Information for SSH access to instances"
  value = var.key_pair_name != "" ? {
    key_pair_name = var.key_pair_name
    security_group = aws_security_group.app.id
    note = "SSH access is available from within the VPC (${data.aws_vpc.main.cidr_block})"
  } : {
    note = "No SSH key pair configured. Set key_pair_name variable to enable SSH access."
  }
} 