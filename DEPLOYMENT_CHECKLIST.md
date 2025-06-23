# Scintilla Production Deployment Checklist

Use this checklist to ensure a successful production deployment of Scintilla to AWS.

## 📋 Pre-Deployment Checklist

### Prerequisites
- [ ] AWS CLI configured with appropriate credentials
- [ ] Terraform v1.0+ installed
- [ ] Docker installed (for containerized deployments)
- [ ] Node.js 18+ and npm installed
- [ ] Python 3.11+ installed

### AWS Account Preparation
- [ ] AWS account with sufficient permissions
- [ ] IAM user/role with required permissions:
  - [ ] EC2 (instances, security groups, load balancers)
  - [ ] RDS (PostgreSQL databases)
  - [ ] VPC (networks, subnets, gateways)
  - [ ] IAM (roles and policies)
  - [ ] KMS (encryption keys)
  - [ ] CloudWatch (logs and metrics)
  - [ ] Auto Scaling (launch templates and groups)
- [ ] AWS region selected (recommended: us-east-1)
- [ ] EC2 key pair created (optional, for SSH access)

### Domain and SSL (Optional)
- [ ] Domain name registered
- [ ] SSL certificate requested in AWS Certificate Manager
- [ ] DNS records configured (if using custom domain)

## 🔧 Configuration Checklist

### Infrastructure Configuration
- [ ] Copy `infra/terraform/terraform.tfvars.example` to `terraform.tfvars`
- [ ] Configure basic settings:
  - [ ] `project_name` set
  - [ ] `environment` set (development/staging/production)
  - [ ] `aws_region` set
- [ ] Configure database settings:
  - [ ] `db_password` set to secure password
  - [ ] `db_instance_class` appropriate for environment
  - [ ] `db_backup_retention_period` set
- [ ] Configure scaling settings:
  - [ ] `instance_type` appropriate for environment
  - [ ] `asg_min_size`, `asg_max_size`, `asg_desired_capacity` set
- [ ] Configure optional settings:
  - [ ] `domain_name` (if using custom domain)
  - [ ] `certificate_arn` (if using SSL)
  - [ ] `key_pair_name` (if SSH access needed)

### Security Configuration
- [ ] Strong database password generated
- [ ] Environment-appropriate deletion protection setting
- [ ] Security groups will be configured automatically
- [ ] KMS key will be created automatically

## 🚀 Deployment Process

### Step 1: Validate Configuration
- [ ] Run deployment script with dry-run:
  ```bash
  ./infra/deploy.sh -e production --dry-run
  ```
- [ ] Review Terraform plan output
- [ ] Verify estimated costs are acceptable
- [ ] Confirm all resources will be created correctly

### Step 2: Execute Deployment
- [ ] Run full deployment:
  ```bash
  ./infra/deploy.sh -e production
  ```
- [ ] Monitor deployment progress
- [ ] Note any warnings or errors
- [ ] Save Terraform outputs for reference

### Step 3: Verify Infrastructure
- [ ] Check Terraform outputs:
  ```bash
  cd infra/terraform
  terraform output
  ```
- [ ] Note down:
  - [ ] Load balancer DNS name
  - [ ] Database endpoint
  - [ ] Application URL
  - [ ] KMS key ID

## ⚙️ Post-Deployment Configuration

### Application Configuration
- [ ] Connect to EC2 instance via SSH (if key pair configured)
- [ ] Configure environment variables in `/opt/scintilla/app/.env`:
  - [ ] `ANTHROPIC_API_KEY` - Your Anthropic API key
  - [ ] `OPENAI_API_KEY` - Your OpenAI API key
  - [ ] `GOOGLE_OAUTH_CLIENT_ID` - Google OAuth client ID
  - [ ] `GOOGLE_OAUTH_CLIENT_SECRET` - Google OAuth client secret
  - [ ] Additional API keys as needed
- [ ] Restart Scintilla service:
  ```bash
  sudo systemctl restart scintilla
  ```

### Health Verification
- [ ] Check application health endpoint:
  ```bash
  curl http://your-load-balancer-dns/health
  ```
- [ ] Verify application is accessible via load balancer
- [ ] Check service status on EC2 instances:
  ```bash
  sudo systemctl status scintilla
  ```
- [ ] Review application logs:
  ```bash
  sudo journalctl -u scintilla -f
  ```

### Database Verification
- [ ] Verify database connectivity from application
- [ ] Check database migrations are applied
- [ ] Verify backup configuration is active
- [ ] Test database performance

## 📊 Monitoring Setup

### CloudWatch Configuration
- [ ] Verify log groups are created:
  - [ ] `/aws/scintilla/application`
  - [ ] `/aws/scintilla/access`
- [ ] Check CloudWatch agent is running on EC2 instances
- [ ] Verify metrics are being collected
- [ ] Set up CloudWatch alarms for:
  - [ ] High error rates
  - [ ] High response times
  - [ ] Database connection issues
  - [ ] High CPU/memory usage

### Log Monitoring
- [ ] Application logs are being collected
- [ ] Access logs are being collected
- [ ] Log retention policies are set correctly
- [ ] Log analysis tools configured (if needed)

## 🔒 Security Verification

### Network Security
- [ ] Security groups configured correctly
- [ ] Application instances in private subnets
- [ ] Database in isolated subnets
- [ ] Load balancer in public subnets only

### Data Security
- [ ] Database encryption at rest enabled
- [ ] KMS key created and functional
- [ ] Credentials encrypted properly
- [ ] SSL/TLS configured (if using custom domain)

### Access Control
- [ ] IAM roles have minimal required permissions
- [ ] SSH access restricted (if enabled)
- [ ] Application authentication working
- [ ] Google OAuth configured and tested

## 🧪 Testing Checklist

### Functional Testing
- [ ] Application loads successfully
- [ ] User authentication works
- [ ] Search functionality works
- [ ] Bot management works
- [ ] Source management works
- [ ] Citations are displayed correctly

### Performance Testing
- [ ] Response times are acceptable
- [ ] Application handles concurrent users
- [ ] Database performance is adequate
- [ ] Auto scaling works correctly

### Integration Testing
- [ ] MCP connections work
- [ ] LLM integrations work
- [ ] Database operations work
- [ ] External API calls work

## 📝 Documentation and Handover

### Deployment Documentation
- [ ] Document all configuration choices
- [ ] Record all passwords and keys securely
- [ ] Document any custom modifications
- [ ] Create operational runbook

### Team Handover
- [ ] Share access credentials securely
- [ ] Provide deployment documentation
- [ ] Train team on monitoring and maintenance
- [ ] Establish incident response procedures

## 🚨 Rollback Plan

### Prepare for Rollback
- [ ] Document current working configuration
- [ ] Keep previous Terraform state
- [ ] Have database backup ready
- [ ] Know how to switch back quickly

### Rollback Procedure
If deployment fails:
1. [ ] Stop new deployment
2. [ ] Revert to previous Terraform state
3. [ ] Restore database if needed
4. [ ] Verify previous version is working
5. [ ] Investigate and fix issues

## 📞 Support Information

### Emergency Contacts
- [ ] DevOps team contact information
- [ ] AWS support contact
- [ ] Application team contacts
- [ ] Escalation procedures documented

### Useful Resources
- [ ] AWS Console bookmarks
- [ ] CloudWatch dashboard URLs
- [ ] Application monitoring URLs
- [ ] Documentation links

---

## ✅ Deployment Sign-off

**Deployment Details:**
- Date: _______________
- Environment: _______________
- Deployed by: _______________
- Terraform version: _______________
- Application version: _______________

**Sign-offs:**
- [ ] Technical Lead: _______________
- [ ] DevOps Lead: _______________
- [ ] Product Owner: _______________

**Notes:**
_Add any deployment-specific notes, issues encountered, or special configurations here._

---

**Next Steps After Deployment:**
1. Monitor application for 24-48 hours
2. Set up regular backup verification
3. Schedule performance review in 1 week
4. Plan for SSL certificate renewal (if applicable)
5. Review and optimize costs after 1 month 