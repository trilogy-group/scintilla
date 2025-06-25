#!/bin/bash
# Scintilla EC2 User Data Script - Resilient Bootstrap
# Downloads and runs the full setup script from GitHub with fallbacks

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

# Comprehensive network debugging
debug_network() {
    echo "=== Network Debug Information ==="
    echo "Network interfaces:"
    ip addr show
    echo ""
    echo "Routing table:"
    ip route show
    echo ""
    echo "DNS configuration:"
    cat /etc/resolv.conf
    echo ""
    echo "Testing connectivity to different endpoints:"
    
    # Test internal AWS services first
    echo "Testing AWS metadata service..."
    if curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/instance-id; then
        echo "✓ AWS metadata service reachable"
    else
        echo "✗ AWS metadata service unreachable"
    fi
    
    # Test DNS resolution
    echo "Testing DNS resolution..."
    if nslookup amazon.com; then
        echo "✓ DNS resolution working"
    else
        echo "✗ DNS resolution failed"
    fi
    
    # Test specific endpoints
    echo "Testing ping to 8.8.8.8 (Google DNS)..."
    ping -c 3 8.8.8.8 || echo "✗ Ping to 8.8.8.8 failed"
    
    echo "Testing ping to 169.254.169.254 (AWS metadata)..."
    ping -c 3 169.254.169.254 || echo "✗ Ping to metadata failed"
    
    # Test HTTP/HTTPS connectivity
    echo "Testing HTTP connectivity to AWS..."
    curl -I --connect-timeout 10 --max-time 15 http://s3.amazonaws.com/ || echo "✗ HTTP to AWS failed"
    
    echo "Testing HTTPS connectivity to AWS..."
    curl -I --connect-timeout 10 --max-time 15 https://s3.amazonaws.com/ || echo "✗ HTTPS to AWS failed"
    
    echo "=== End Network Debug ==="
}

# Test network connectivity with detailed debugging
echo "Starting comprehensive network tests..."
debug_network

# Wait a bit for network to stabilize, then test again
echo "Waiting 30 seconds for network to stabilize..."
sleep 30
echo "Testing network again after wait..."

# Test with timeout and retries
test_connectivity() {
    local target="$1"
    local description="$2"
    local max_attempts=3
    
    for attempt in $(seq 1 $max_attempts); do
        echo "Testing $description (attempt $attempt/$max_attempts)..."
        if ping -c 3 -W 5 "$target"; then
            echo "✓ $description successful"
            return 0
        else
            echo "✗ $description failed (attempt $attempt)"
            if [ $attempt -lt $max_attempts ]; then
                echo "Retrying in 10 seconds..."
                sleep 10
            fi
        fi
    done
    return 1
}

# Test multiple connectivity targets
connectivity_ok=false
if test_connectivity "8.8.8.8" "Google DNS"; then
    connectivity_ok=true
elif test_connectivity "1.1.1.1" "Cloudflare DNS"; then
    connectivity_ok=true
elif test_connectivity "169.254.169.254" "AWS Metadata"; then
    echo "Limited connectivity - AWS metadata reachable"
    connectivity_ok=true
fi

if [ "$connectivity_ok" = false ]; then
    echo "ERROR: No internet connectivity detected - creating minimal application"
    create_minimal_app
    exit 0
fi

# Test DNS resolution
echo "Testing DNS resolution..."
if ! nslookup github.com; then
    echo "WARNING: DNS resolution failed for github.com"
    # Try setting alternative DNS
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf
    echo "nameserver 1.1.1.1" >> /etc/resolv.conf
    if ! nslookup github.com; then
        echo "ERROR: DNS resolution still failing - creating minimal application"
        create_minimal_app
        exit 0
    fi
fi

# Export all variables for the setup script
export DB_HOST DB_NAME DB_USERNAME DB_PASSWORD KMS_KEY_ID AWS_REGION
export GITHUB_REPOSITORY_URL GITHUB_TOKEN 
export ANTHROPIC_API_KEY OPENAI_API_KEY DEFAULT_LLM_PROVIDER
export GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET ALLOWED_DOMAINS
export DEBUG_MODE TEST_MODE

# Function to create minimal working application
create_minimal_app() {
    echo "Creating minimal Scintilla application..."
    
    # Update system packages
    yum update -y
    yum install -y python3 python3-pip nginx
    
    # Create application structure
    mkdir -p /opt/scintilla/app/src
    useradd -m -s /bin/bash scintilla || true
    chown -R scintilla:scintilla /opt/scintilla
    
    # Create minimal requirements
    cat > /opt/scintilla/app/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
psycopg2-binary==2.9.9
EOF
    
    python3 -m pip install -r /opt/scintilla/app/requirements.txt
    
    # Create minimal main.py
    cat > /opt/scintilla/app/src/main.py << 'EOF'
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="Scintilla", description="AI Search Platform")

@app.get("/health")
def health_check():
    return JSONResponse({"status": "healthy", "message": "Scintilla is running"})

@app.get("/")
def root():
    return JSONResponse({"message": "Scintilla is ready", "docs": "/docs"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
    
    chown -R scintilla:scintilla /opt/scintilla
    
    # Create systemd service
    cat > /etc/systemd/system/scintilla.service << 'EOF'
[Unit]
Description=Scintilla AI Search Platform
After=network.target

[Service]
Type=simple
User=scintilla
Group=scintilla
WorkingDirectory=/opt/scintilla/app
ExecStart=/usr/bin/python3 src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Configure nginx
    cat > /etc/nginx/conf.d/scintilla.conf << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
EOF
    
    rm -f /etc/nginx/conf.d/default.conf
    
    # Start services
    systemctl daemon-reload
    systemctl start nginx && systemctl enable nginx
    systemctl start scintilla && systemctl enable scintilla
    
    echo "Minimal Scintilla application started successfully"
}

# Try to download setup script from GitHub with retries
download_setup_script() {
    local max_retries=5
    local retry_delay=15
    
    for i in $(seq 1 $max_retries); do
        echo "Attempt $i/$max_retries: Downloading setup script from GitHub..."
        
        if [ -n "$GITHUB_TOKEN" ]; then
            # Download with authentication
            if curl --connect-timeout 30 --max-time 180 \
                   -H "Authorization: token $GITHUB_TOKEN" \
                   -H "Accept: application/vnd.github.v3.raw" \
                   -L "https://api.github.com/repos/trilogy-group/scintilla/contents/infra/setup_ec2.sh" \
                   -o /tmp/setup_ec2.sh; then
                echo "Setup script downloaded successfully"
                return 0
            fi
        else
            # Download without authentication
            if curl --connect-timeout 30 --max-time 180 \
                   -L "https://raw.githubusercontent.com/trilogy-group/scintilla/main/infra/setup_ec2.sh" \
                   -o /tmp/setup_ec2.sh; then
                echo "Setup script downloaded successfully"
                return 0
            fi
        fi
        
        echo "Download attempt $i failed, retrying in $retry_delay seconds..."
        sleep $retry_delay
    done
    
    echo "Failed to download setup script after $max_retries attempts"
    return 1
}

# Main execution
if download_setup_script; then
    echo "Running full setup script..."
    chmod +x /tmp/setup_ec2.sh
    /tmp/setup_ec2.sh
else
    echo "GitHub download failed, creating minimal application..."
    create_minimal_app
fi

echo "Bootstrap completed at $(date)" 