# Scintilla Terraform Variables
# Configure deployment parameters for different environments

# Project Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "scintilla"
}

variable "environment" {
  description = "Environment (development, staging, production)"
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production."
  }
}

# AWS Configuration
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Existing Infrastructure Configuration
variable "existing_vpc_id" {
  description = "ID of the existing VPC to use"
  type        = string
  default     = "vpc-0ecd69c2cad874a73"
}

# Network Configuration (legacy - kept for compatibility but not used with existing VPC)
variable "vpc_cidr" {
  description = "CIDR block for VPC (not used when using existing VPC)"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (not used when using existing VPC)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (not used when using existing VPC)"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets (these will be created)"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets (not used when using existing VPC)"
  type        = bool
  default     = true
}

# Application Configuration
variable "app_port" {
  description = "Port on which the application runs"
  type        = number
  default     = 8000
}

# EC2 Configuration
variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "ami_id" {
  description = "AMI ID for EC2 instances"
  type        = string
  default     = "ami-05ffe3c48a9991133" # Amazon Linux 2023 in us-east-1
}

variable "key_pair_name" {
  description = "Name of the EC2 Key Pair for SSH access"
  type        = string
  default     = ""
}

# Auto Scaling Configuration
variable "asg_min_size" {
  description = "Minimum number of instances in Auto Scaling Group"
  type        = number
  default     = 1
}

variable "asg_max_size" {
  description = "Maximum number of instances in Auto Scaling Group"
  type        = number
  default     = 10
}

variable "asg_desired_capacity" {
  description = "Desired number of instances in Auto Scaling Group"
  type        = number
  default     = 2
}

# Repository Configuration
variable "github_repository_url" {
  description = "GitHub repository URL for the application"
  type        = string
  default     = "https://github.com/trilogy-group/scintilla.git"
}

variable "github_token" {
  description = "GitHub personal access token for repository access"
  type        = string
  sensitive   = true
  default     = ""
}

# Application Environment Variables
variable "anthropic_api_key" {
  description = "Anthropic API key for Claude"
  type        = string
  sensitive   = true
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "default_llm_provider" {
  description = "Default LLM provider (anthropic or openai)"
  type        = string
  default     = "anthropic"
}

variable "google_oauth_client_id" {
  description = "Google OAuth Client ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_oauth_client_secret" {
  description = "Google OAuth Client Secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "allowed_domains" {
  description = "Comma-separated list of allowed domains for authentication"
  type        = string
  default     = "ignitetech.com,ignitetech.ai"
}

variable "debug_mode" {
  description = "Enable debug mode"
  type        = bool
  default     = false
}

variable "test_mode" {
  description = "Enable test mode (disables real MCP connections)"
  type        = bool
  default     = false
}

# Database Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.8"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "scintilla"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "scintilla"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for RDS instance (GB)"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS instance (GB)"
  type        = number
  default     = 100
}

variable "db_backup_retention_period" {
  description = "Number of days to retain database backups"
  type        = number
  default     = 7
}

variable "db_backup_window" {
  description = "Preferred backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "db_maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

# Monitoring Configuration
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
}

# Domain Configuration (optional)
variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ARN of the SSL certificate in ACM"
  type        = string
  default     = ""
}

# Feature Flags
variable "enable_enhanced_monitoring" {
  description = "Enable enhanced monitoring for RDS"
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for resources"
  type        = bool
  default     = false
}

# ===================================================================
# Environment-specific configurations
# ===================================================================

locals {
  environment_configs = {
    development = {
      instance_type                = "t3.micro"
      db_instance_class           = "db.t3.micro"
      asg_min_size                = 1
      asg_max_size                = 2
      asg_desired_capacity        = 1
      enable_nat_gateway          = false
      enable_deletion_protection  = false
      db_backup_retention_period  = 1
      log_retention_days          = 7
    }
    staging = {
      instance_type                = "t3.small"
      db_instance_class           = "db.t3.small"
      asg_min_size                = 1
      asg_max_size                = 4
      asg_desired_capacity        = 2
      enable_nat_gateway          = true
      enable_deletion_protection  = false
      db_backup_retention_period  = 3
      log_retention_days          = 14
    }
    production = {
      instance_type                = "t3.medium"
      db_instance_class           = "db.r5.large"
      asg_min_size                = 2
      asg_max_size                = 10
      asg_desired_capacity        = 3
      enable_nat_gateway          = true
      enable_deletion_protection  = true
      db_backup_retention_period  = 7
      log_retention_days          = 30
    }
  }

  # Merge environment-specific config with user overrides
  config = merge(
    local.environment_configs[var.environment],
    {
      instance_type                = var.instance_type != "t3.medium" ? var.instance_type : local.environment_configs[var.environment].instance_type
      db_instance_class           = var.db_instance_class != "db.t3.micro" ? var.db_instance_class : local.environment_configs[var.environment].db_instance_class
      asg_min_size                = var.asg_min_size != 1 ? var.asg_min_size : local.environment_configs[var.environment].asg_min_size
      asg_max_size                = var.asg_max_size != 10 ? var.asg_max_size : local.environment_configs[var.environment].asg_max_size
      asg_desired_capacity        = var.asg_desired_capacity != 2 ? var.asg_desired_capacity : local.environment_configs[var.environment].asg_desired_capacity
      enable_nat_gateway          = var.enable_nat_gateway != true ? var.enable_nat_gateway : local.environment_configs[var.environment].enable_nat_gateway
      enable_deletion_protection  = var.enable_deletion_protection != false ? var.enable_deletion_protection : local.environment_configs[var.environment].enable_deletion_protection
      db_backup_retention_period  = var.db_backup_retention_period != 7 ? var.db_backup_retention_period : local.environment_configs[var.environment].db_backup_retention_period
      log_retention_days          = var.log_retention_days != 14 ? var.log_retention_days : local.environment_configs[var.environment].log_retention_days
    }
  )
} 