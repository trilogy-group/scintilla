# Scintilla AWS Deployment Guide

This guide provides comprehensive instructions for deploying Scintilla to AWS using infrastructure as code and best practices.

## 🚀 Quick Start

```bash
# 1. Copy and customize configuration
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars

# 2. Deploy to development
./infra/deploy.sh -e development

# 3. Deploy to production
./infra/deploy.sh -e production
```

## 📋 Prerequisites

### Required Tools
- **AWS CLI** v2.0+ configured with appropriate credentials
- **Terraform** v1.0+ for infrastructure as code
- **Docker** for containerization (optional)
- **Node.js** 18+ for frontend builds
- **Python** 3.11+ for backend

### AWS Requirements
- AWS account with appropriate permissions
- Configured AWS credentials (`aws configure` or IAM roles)
- Domain name (optional, for custom domains)
- SSL certificate in AWS Certificate Manager (optional)

### Required AWS Permissions
Your AWS user/role needs permissions for:
- **EC2**: Create instances, security groups, load balancers
- **RDS**: Create PostgreSQL databases
- **VPC**: Create VPCs, subnets, internet gateways
- **IAM**: Create roles and policies for application
- **KMS**: Create and manage encryption keys
- **CloudWatch**: Create log groups and metrics
- **Auto Scaling**: Create launch templates and groups

## 🏗️ Architecture Overview

### Infrastructure Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Internet      │    │  Application     │    │   Database      │
│   Gateway       │────│  Load Balancer   │────│   (RDS)         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │  Auto Scaling   │
                       │     Group       │
                       └─────────────────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
            ┌───────▼───┐ ┌────▼────┐ ┌───▼────┐
            │   EC2     │ │  EC2    │ │  EC2   │
            │Instance 1 │ │Instance │ │Instance│
            └───────────┘ └─────────┘ └────────┘
```

### Network Architecture
- **VPC**: Isolated network environment
- **Public Subnets**: Load balancer and NAT gateway
- **Private Subnets**: Application instances
- **Database Subnets**: RDS instances (isolated)
- **Security Groups**: Granular firewall rules

### Security Features
- **KMS Encryption**: All data encrypted at rest and in transit
- **IAM Roles**: Least privilege access for EC2 instances
- **Security Groups**: Network-level access control
- **Private Subnets**: Application servers not directly accessible
- **SSL/TLS**: HTTPS termination at load balancer

## 🔧 Configuration

### 1. Basic Configuration

Copy the example configuration:
```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Edit `infra/terraform/terraform.tfvars`:
```hcl
# Basic Configuration
project_name = "scintilla"
environment  = "production"
aws_region   = "us-east-1"

# Database Configuration
db_password = "your-secure-password-here"

# Optional: Custom Domain
domain_name     = "scintilla.yourdomain.com"
certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/..."

# SSH Access (optional)
key_pair_name = "your-ec2-key-pair"
```

### 2. Environment-Specific Settings

#### Development Environment
```hcl
environment = "development"
instance_type = "t3.micro"
db_instance_class = "db.t3.micro"
asg_min_size = 1
asg_max_size = 2
enable_nat_gateway = false  # Save costs
enable_deletion_protection = false
```

#### Staging Environment
```hcl
environment = "staging"
instance_type = "t3.small"
db_instance_class = "db.t3.small"
asg_min_size = 1
asg_max_size = 4
enable_nat_gateway = true
enable_deletion_protection = false
```

#### Production Environment
```hcl
environment = "production"
instance_type = "t3.medium"
db_instance_class = "db.r5.large"
asg_min_size = 2
asg_max_size = 10
enable_nat_gateway = true
enable_deletion_protection = true
```

## 🚀 Deployment Methods

### Method 1: Automated Script (Recommended)

Use the provided deployment script for streamlined deployments:

```bash
# Development deployment
./infra/deploy.sh -e development

# Production deployment with dry run first
./infra/deploy.sh -e production --dry-run
./infra/deploy.sh -e production

# Skip tests and builds for faster deployment
./infra/deploy.sh -e staging --skip-tests --skip-build
```

**Advantages:**
- Single command deployment
- Built-in validation and testing
- Environment-specific configurations
- Comprehensive error handling

### Method 2: Manual Terraform

For advanced users who want full control:

**Deployment Steps:**

1. **Initialize and Plan**
   ```bash
   cd infra/terraform
   terraform init
   terraform plan -var-file="terraform.tfvars"
   ```

2. **Deploy Infrastructure**
   ```bash
   terraform apply -var-file="terraform.tfvars"
   ```

3. **Configure Application**
   ```bash
   # Get database endpoint from Terraform output
   terraform output database_endpoint
   
   # Get application URL
   terraform output application_url
   ```

**Advantages:**
- Infrastructure as Code
- Version controlled
- Repeatable deployments
- Environment parity
- Easy rollbacks

## ⚙️ Post-Deployment Configuration

### 1. Environment Variables

After deployment, configure these environment variables on your EC2 instances:

```bash
# Connect to EC2 instance
ssh -i your-key.pem ec2-user@your-instance-ip

# Edit environment file
sudo -u scintilla nano /opt/scintilla/app/.env
```

Required environment variables:
```bash
# LLM API Keys
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Hive Integration (if applicable)
HIVE_API_KEY=your-hive-key
```

### 2. Health Checks

Verify deployment health:
```bash
# Check application health
curl http://your-load-balancer-dns/health

# Check service status
ssh -i your-key.pem ec2-user@your-instance-ip
sudo systemctl status scintilla
```

### 3. SSL Certificate (Optional)

If using a custom domain:

1. **Create SSL Certificate in ACM**
   ```bash
   aws acm request-certificate \
     --domain-name scintilla.yourdomain.com \
     --validation-method DNS
   ```

2. **Update Load Balancer**
   - Add HTTPS listener
   - Configure certificate
   - Redirect HTTP to HTTPS

## 📊 Monitoring and Logging

### CloudWatch Integration

The deployment automatically configures:
- **Application Logs**: `/aws/scintilla/application`
- **Access Logs**: `/aws/scintilla/access`
- **System Metrics**: CPU, memory, disk usage
- **Custom Metrics**: Application-specific metrics

### Accessing Logs
```bash
# View application logs
aws logs tail /aws/scintilla/application --follow

# View access logs
aws logs tail /aws/scintilla/access --follow
```

### Monitoring Dashboard

Create CloudWatch dashboards for:
- Application performance metrics
- Database performance
- Load balancer metrics
- Auto Scaling activities
- Error rates and response times

## 🔧 Maintenance

### Updates and Patches

1. **Application Updates**
   ```bash
   # Deploy new version
   ./infra/deploy.sh -e production -m terraform
   
   # Rolling update via Auto Scaling
   aws autoscaling start-instance-refresh \
     --auto-scaling-group-name scintilla-production-asg
   ```

2. **Infrastructure Updates**
   ```bash
   # Plan changes
   terraform plan -var-file="terraform.tfvars"
   
   # Apply changes
   terraform apply -var-file="terraform.tfvars"
   ```

### Backup and Recovery

1. **Database Backups**
   - Automatic daily backups configured
   - Point-in-time recovery available
   - Cross-region backup replication (optional)

2. **Application Data**
   - User data stored in RDS (automatically backed up)
   - Configuration stored in version control

### Scaling

1. **Horizontal Scaling**
   ```bash
   # Update Auto Scaling Group
   aws autoscaling update-auto-scaling-group \
     --auto-scaling-group-name scintilla-production-asg \
     --desired-capacity 5
   ```

2. **Vertical Scaling**
   ```bash
   # Update instance type in terraform.tfvars
   instance_type = "t3.large"
   
   # Apply changes
   terraform apply -var-file="terraform.tfvars"
   ```

## 💰 Cost Optimization

### Development Environment
- **Estimated Cost**: $50-100/month
- Use `t3.micro` instances
- Disable NAT Gateway
- Single AZ deployment
- Minimal backup retention

### Staging Environment
- **Estimated Cost**: $150-250/month
- Use `t3.small` instances
- Enable NAT Gateway
- Multi-AZ for testing
- Moderate backup retention

### Production Environment
- **Estimated Cost**: $500-1000/month
- Use `t3.medium`+ instances
- Multi-AZ deployment
- Enhanced monitoring
- Full backup retention
- Reserved instances for 40% savings

### Cost Optimization Tips

1. **Reserved Instances**: Save 40-60% on compute costs
2. **Spot Instances**: Use for development/staging (up to 90% savings)
3. **Right-sizing**: Monitor and adjust instance sizes
4. **Lifecycle Policies**: Automatically delete old logs and backups
5. **Scheduled Scaling**: Scale down during off-hours

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Check security groups
   # Verify database endpoint
   # Test connection from EC2 instance
   ```

2. **Load Balancer Health Check Failures**
   ```bash
   # Check application health endpoint
   # Verify security group rules
   # Check application logs
   ```

3. **Auto Scaling Issues**
   ```bash
   # Check launch template
   # Verify IAM roles
   # Review user data script logs
   ```

### Debugging Commands

```bash
# Check application status
sudo systemctl status scintilla

# View application logs
sudo journalctl -u scintilla -f

# Check user data script logs
sudo cat /var/log/user-data.log

# Test database connectivity
python3 -c "import psycopg2; conn = psycopg2.connect('your-db-url')"
```

## 🔄 CI/CD Integration (Future)

The infrastructure is designed to support CI/CD pipelines:

### GitHub Actions Integration
```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to AWS
        run: ./infra/deploy.sh -e production -m terraform --force
```

### Deployment Strategies
- **Blue-Green Deployments**: Zero-downtime deployments
- **Rolling Updates**: Gradual instance replacement
- **Canary Deployments**: Test with subset of traffic

## 📚 Additional Resources

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [PostgreSQL on RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)

## 🆘 Support

For deployment issues:
1. Check the troubleshooting section above
2. Review CloudWatch logs
3. Consult the AWS documentation
4. Contact the development team

---

**Note**: This deployment guide assumes you have appropriate AWS permissions and understand basic AWS concepts. For production deployments, consider involving your DevOps or infrastructure team. 