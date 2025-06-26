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

# Function to create minimal working application (defined early)
create_minimal_app() {
    echo "Creating minimal Scintilla application..."
    
    # Update system packages
    dnf update -y
    dnf install -y python3.11 python3.11-pip python3.11-devel nginx
    
    # Set up Python 3.11 as default python3
    alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1
    echo "Python version: $(python3 --version)"
    
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
    
    python3.11 -m pip install --upgrade pip
    python3.11 -m pip install -r /opt/scintilla/app/requirements.txt
    
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
        echo "[OK] AWS metadata service reachable"
    else
        echo "[FAIL] AWS metadata service unreachable"
    fi
    
    # Test DNS resolution
    echo "Testing DNS resolution..."
    if nslookup amazon.com; then
        echo "[OK] DNS resolution working"
    else
        echo "[FAIL] DNS resolution failed"
    fi
    
    # Test HTTP/HTTPS connectivity (this is what actually matters)
    echo "Testing HTTP connectivity to AWS..."
    if curl -I --connect-timeout 10 --max-time 15 http://s3.amazonaws.com/ 2>/dev/null | grep -q "HTTP"; then
        echo "[OK] HTTP to AWS working"
    else
        echo "[FAIL] HTTP to AWS failed"
    fi
    
    echo "Testing HTTPS connectivity to AWS..."
    if curl -I --connect-timeout 10 --max-time 15 https://s3.amazonaws.com/ 2>/dev/null | grep -q "HTTP"; then
        echo "[OK] HTTPS to AWS working"
    else
        echo "[FAIL] HTTPS to AWS failed"
    fi
    
    echo "=== End Network Debug ==="
}

# Test HTTP connectivity (not ping, since ping often fails but HTTP works)
test_http_connectivity() {
    echo "Testing HTTP connectivity to determine if internet is available..."
    
    # Test multiple endpoints without using array syntax that confuses Terraform
    echo "Testing: http://s3.amazonaws.com/"
    if curl -I --connect-timeout 10 --max-time 15 "http://s3.amazonaws.com/" 2>/dev/null | grep -q "HTTP"; then
        echo "[OK] HTTP connectivity confirmed via http://s3.amazonaws.com/"
        return 0
    fi
    
    echo "Testing: https://s3.amazonaws.com/"
    if curl -I --connect-timeout 10 --max-time 15 "https://s3.amazonaws.com/" 2>/dev/null | grep -q "HTTP"; then
        echo "[OK] HTTP connectivity confirmed via https://s3.amazonaws.com/"
        return 0
    fi
    
    echo "Testing: http://amazon.com/"
    if curl -I --connect-timeout 10 --max-time 15 "http://amazon.com/" 2>/dev/null | grep -q "HTTP"; then
        echo "[OK] HTTP connectivity confirmed via http://amazon.com/"
        return 0
    fi
    
    echo "Testing: https://api.github.com/"
    if curl -I --connect-timeout 10 --max-time 15 "https://api.github.com/" 2>/dev/null | grep -q "HTTP"; then
        echo "[OK] HTTP connectivity confirmed via https://api.github.com/"
        return 0
    fi
    
    echo "[FAIL] No HTTP connectivity detected"
    return 1
}

# Test network connectivity with detailed debugging
echo "Starting comprehensive network tests..."
debug_network

# Wait a bit for network to stabilize, then test again
echo "Waiting 10 seconds for network to stabilize..."
sleep 10
echo "Testing HTTP connectivity..."

# Use HTTP connectivity test instead of ping
if test_http_connectivity; then
    echo "[OK] Internet connectivity confirmed - proceeding with full setup"
    connectivity_ok=true
else
    echo "[FAIL] No reliable internet connectivity - will create minimal application"
    connectivity_ok=false
fi

# Test DNS resolution
if [ "$connectivity_ok" = true ]; then
    echo "Testing DNS resolution..."
    if ! nslookup github.com; then
        echo "WARNING: DNS resolution failed for github.com"
        # Try setting alternative DNS
        echo "nameserver 8.8.8.8" >> /etc/resolv.conf
        echo "nameserver 1.1.1.1" >> /etc/resolv.conf
        if ! nslookup github.com; then
            echo "ERROR: DNS resolution still failing - creating minimal application"
            connectivity_ok=false
        fi
    fi
fi

# Export all variables for the setup script
export DB_HOST DB_NAME DB_USERNAME DB_PASSWORD KMS_KEY_ID AWS_REGION
export GITHUB_REPOSITORY_URL GITHUB_TOKEN 
export ANTHROPIC_API_KEY OPENAI_API_KEY DEFAULT_LLM_PROVIDER
export GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET ALLOWED_DOMAINS
export DEBUG_MODE TEST_MODE

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
if [ "$connectivity_ok" = true ] && download_setup_script; then
    echo "Running full setup script..."
    chmod +x /tmp/setup_ec2.sh
    /tmp/setup_ec2.sh
else
    echo "Creating minimal application due to connectivity or download issues..."
    create_minimal_app
fi

echo "Bootstrap completed at $(date)" 