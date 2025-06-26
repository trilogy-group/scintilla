# Scintilla AWS Infrastructure - Terraform Configuration
# Production-ready deployment with security best practices

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Uncomment for remote state management
  # backend "s3" {
  #   bucket = "scintilla-terraform-state"
  #   key    = "infrastructure/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "Scintilla"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "IgniteTech"
    }
  }
}

# Data sources for existing infrastructure
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Use existing VPC instead of creating new one
data "aws_vpc" "main" {
  id = var.existing_vpc_id
}

# Use existing Internet Gateway
data "aws_internet_gateway" "main" {
  filter {
    name   = "attachment.vpc-id"
    values = [data.aws_vpc.main.id]
  }
}

# Use existing subnets - find all subnets first, then filter
data "aws_subnets" "all" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
}

# Try to find public subnets more broadly
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["true"]
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["false"]
  }
  # Remove the Type tag filter to be more flexible with existing subnets
}

# Use existing private subnets for database - select first 2 for multi-AZ
data "aws_subnets" "database" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  filter {
    name   = "map-public-ip-on-launch"
    values = ["false"]
  }
}

# ALB subnet selection - requires 2 subnets in different AZs
locals {
  # Use both available subnets from different AZs for ALB
  alb_subnets = [
    "subnet-071090cb33bb5d24a",   # Public subnet (us-east-1a)
    "subnet-07267589d18bc0008"    # Private subnet (us-east-1c) - ALB can use mixed public/private
  ]
}

# Security Groups (these we still create)
resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}

resource "aws_security_group" "app" {
  name_prefix = "${var.project_name}-app-"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    description     = "HTTP from ALB"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  # Allow all outbound traffic (instances are in private subnets, so this is secure)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-app-sg"
  }
}

resource "aws_security_group" "database" {
  name_prefix = "${var.project_name}-db-"
  vpc_id      = data.aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  tags = {
    Name = "${var.project_name}-database-sg"
  }
}

# KMS Key for encryption
resource "aws_kms_key" "main" {
  description             = "KMS key for ${var.project_name} encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-kms-key"
  }
}

resource "aws_kms_alias" "main" {
  name          = "alias/${var.project_name}-key"
  target_key_id = aws_kms_key.main.key_id
}

# Database Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = data.aws_subnets.database.ids

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

# RDS PostgreSQL Database
resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-${var.environment}"

  # Engine configuration
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.db_instance_class

  # Storage configuration
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id           = aws_kms_key.main.arn

  # Database configuration
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false

  # Backup configuration
  backup_retention_period = var.db_backup_retention_period
  backup_window          = var.db_backup_window
  maintenance_window     = var.db_maintenance_window

  # High availability
  multi_az = var.environment == "production" ? true : false

  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  # Deletion protection
  deletion_protection = var.environment == "production" ? true : false
  skip_final_snapshot = var.environment != "production"

  tags = {
    Name = "${var.project_name}-database"
  }
}

# IAM Role for RDS Enhanced Monitoring
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.project_name}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Application Load Balancer - use existing subnets
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = local.alb_subnets

  enable_deletion_protection = var.environment == "production" ? true : false

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_lb_target_group" "app" {
  name     = "${var.project_name}-app-tg"
  port     = var.app_port
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name = "${var.project_name}-app-tg"
  }
}

# HTTP Listener - redirect to HTTPS when certificate is available
resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = var.certificate_arn != "" ? "redirect" : "forward"
    
    # Redirect to HTTPS when certificate is available
    dynamic "redirect" {
      for_each = var.certificate_arn != "" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
    
    # Forward to target group when no certificate (development)
    target_group_arn = var.certificate_arn != "" ? null : aws_lb_target_group.app.arn
  }
}

# HTTPS Listener (for custom domain)
resource "aws_lb_listener" "app_https" {
  count             = var.certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Launch Configuration for Auto Scaling (using simplified user_data)
resource "aws_launch_configuration" "app" {
  name_prefix          = "${var.project_name}-"
  image_id             = var.ami_id
  instance_type        = var.instance_type
  key_name             = var.key_pair_name
  security_groups      = [aws_security_group.app.id]
  iam_instance_profile = aws_iam_instance_profile.app.name

  user_data = base64encode(templatefile("${path.module}/user_data_simple.sh", {
    db_host                    = aws_db_instance.main.address
    db_name                    = aws_db_instance.main.db_name
    db_username                = aws_db_instance.main.username
    db_password                = var.db_password
    kms_key_id                 = aws_kms_key.main.key_id
    region                     = var.aws_region
    github_repository_url      = var.github_repository_url
    github_token               = var.github_token
    anthropic_api_key          = var.anthropic_api_key
    openai_api_key             = var.openai_api_key
    default_llm_provider       = var.default_llm_provider
    google_oauth_client_id     = var.google_oauth_client_id
    google_oauth_client_secret = var.google_oauth_client_secret
    allowed_domains            = var.allowed_domains
    debug_mode                 = var.debug_mode
    test_mode                  = var.test_mode
  }))

  lifecycle {
    create_before_destroy = true
  }
}

# Service-linked role for Auto Scaling already exists in this account

# IAM Role for EC2 instances
resource "aws_iam_role" "app" {
  name = "${var.project_name}-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "app" {
  name = "${var.project_name}-app-policy"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt"
        ]
        Resource = [aws_kms_key.main.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream", 
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/scintilla/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeTags",
          "ec2:DescribeImages",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeLaunchTemplates",
          "ec2:DescribeLaunchTemplateVersions",
          "ec2:RunInstances",
          "ec2:CreateTags",
          "ec2:TerminateInstances",
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeLaunchTemplates",
          "autoscaling:CreateAutoScalingGroup",
          "autoscaling:UpdateAutoScalingGroup",
          "autoscaling:DeleteAutoScalingGroup",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetHealth"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-app-role"
        ]
      }
    ]
  })
}

# Additional IAM role policy for Auto Scaling and Launch Template permissions
resource "aws_iam_role_policy_attachment" "app_systems_manager" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.project_name}-app-profile"
  role = aws_iam_role.app.name
}

# Auto Scaling Group - use only NAT Gateway subnet for reliable internet access
resource "aws_autoscaling_group" "app" {
  name                = "${var.project_name}-asg"
  vpc_zone_identifier = ["subnet-04121b354df4d865a"]
  target_group_arns   = [aws_lb_target_group.app.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = var.asg_min_size
  max_size         = var.asg_max_size
  desired_capacity = var.asg_desired_capacity

  launch_configuration = aws_launch_configuration.app.name

  # Explicit dependencies
  depends_on = [
    aws_launch_configuration.app,
    aws_iam_instance_profile.app,
    aws_iam_role_policy.app
  ]

  tag {
    key                 = "Name"
    value               = "${var.project_name}-asg-instance"
    propagate_at_launch = true
  }

  tag {
    key                 = "Project"
    value               = var.project_name
    propagate_at_launch = true
  }

  tag {
    key                 = "Environment"
    value               = var.environment
    propagate_at_launch = true
  }
}

# Auto Scaling Policies
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "${var.project_name}-scale-up"
  scaling_adjustment     = 1
  adjustment_type        = "ChangeInCapacity"
  cooldown              = 300
  autoscaling_group_name = aws_autoscaling_group.app.name
}

resource "aws_autoscaling_policy" "scale_down" {
  name                   = "${var.project_name}-scale-down"
  scaling_adjustment     = -1
  adjustment_type        = "ChangeInCapacity"
  cooldown              = 300
  autoscaling_group_name = aws_autoscaling_group.app.name
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.project_name}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors ec2 cpu utilization"
  alarm_actions       = [aws_autoscaling_policy.scale_up.arn]

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app.name
  }

  tags = {
    Name = "${var.project_name}-cpu-high-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "cpu_low" {
  alarm_name          = "${var.project_name}-cpu-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "10"
  alarm_description   = "This metric monitors ec2 cpu utilization"
  alarm_actions       = [aws_autoscaling_policy.scale_down.arn]

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app.name
  }

  tags = {
    Name = "${var.project_name}-cpu-low-alarm"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/scintilla/application"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-app-logs"
  }
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/scintilla/access"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-access-logs"
  }
}

 