#!/bin/bash
# Scintilla EC2 User Data Script - Minimal Bootstrap
# Downloads and runs the full setup script from GitHub

set -euo pipefail

# Variables passed from Terraform
DB_HOST="${db_host}"
DB_NAME="${db_name}"
DB_USERNAME="${db_username}"
DB_PASSWORD="${db_password}"
KMS_KEY_ID="${kms_key_id}"
AWS_REGION="${region}"
GITHUB_REPOSITORY_URL="${github_repository_url}"
GITHUB_TOKEN="${github_token}"
ANTHROPIC_API_KEY="${anthropic_api_key}"
OPENAI_API_KEY="${openai_api_key}"
DEFAULT_LLM_PROVIDER="${default_llm_provider}"
GOOGLE_OAUTH_CLIENT_ID="${google_oauth_client_id}"
GOOGLE_OAUTH_CLIENT_SECRET="${google_oauth_client_secret}"
ALLOWED_DOMAINS="${allowed_domains}"
DEBUG_MODE="${debug_mode}"
TEST_MODE="${test_mode}"

# Logging
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
echo "Starting Scintilla bootstrap at $(date)"

# Export all variables for the setup script
export DB_HOST DB_NAME DB_USERNAME DB_PASSWORD KMS_KEY_ID AWS_REGION
export GITHUB_REPOSITORY_URL GITHUB_TOKEN 
export ANTHROPIC_API_KEY OPENAI_API_KEY DEFAULT_LLM_PROVIDER
export GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET ALLOWED_DOMAINS
export DEBUG_MODE TEST_MODE

# Download and run the full setup script from GitHub
echo "Downloading setup script from GitHub..."
if [ -n "$GITHUB_TOKEN" ]; then
    # Download setup script with authentication
    curl -H "Authorization: token $GITHUB_TOKEN" \
         -H "Accept: application/vnd.github.v3.raw" \
         -L "https://api.github.com/repos/trilogy-group/scintilla/contents/infra/setup_ec2.sh" \
         -o /tmp/setup_ec2.sh
else
    # Download setup script without authentication (if public)
    curl -L "https://raw.githubusercontent.com/trilogy-group/scintilla/main/infra/setup_ec2.sh" \
         -o /tmp/setup_ec2.sh
fi

# Make script executable and run it
chmod +x /tmp/setup_ec2.sh
echo "Running full setup script..."
/tmp/setup_ec2.sh

echo "Bootstrap completed at $(date)" 