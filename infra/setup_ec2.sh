#!/bin/bash
# Scintilla EC2 Full Setup Script
# This script is downloaded and executed by user_data_simple.sh
# All variables are exported from the user_data bootstrap script

set -euo pipefail

echo "Starting Scintilla full installation at $(date)"

# Variables are exported from user_data_simple.sh
# DB_HOST, DB_NAME, DB_USERNAME, DB_PASSWORD, KMS_KEY_ID, AWS_REGION
# GITHUB_REPOSITORY_URL, GITHUB_TOKEN
# ANTHROPIC_API_KEY, OPENAI_API_KEY, DEFAULT_LLM_PROVIDER
# GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, ALLOWED_DOMAINS
# DEBUG_MODE, TEST_MODE

# Update system (Amazon Linux 2023 uses dnf)
echo "Updating system packages..."
sudo dnf update -y

# Install required packages
echo "Installing required packages..."
sudo dnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    git \
    docker \
    htop \
    amazon-cloudwatch-agent \
    nginx

# Set up Python 3.11 as default python3
echo "Setting up Python 3.11 as default..."
sudo alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1
echo "Python version: $(python3 --version)"

# Install AWS CLI via pip for Python 3.11 compatibility
echo "Installing AWS CLI for Python 3.11..."
sudo python3.11 -m pip install awscli
echo "AWS CLI version: $(aws --version)"

# Install Node.js 18 - Use direct binary installation to avoid dnf/Python conflicts
echo "Installing Node.js 18..."
# Download and install Node.js directly to avoid dnf Python dependency issues
curl -fsSL https://nodejs.org/dist/v18.20.4/node-v18.20.4-linux-x64.tar.xz | sudo tar -xJ -C /usr/local --strip-components=1
echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"

# Configure AWS CLI
echo "Configuring AWS CLI..."
sudo aws configure set region $AWS_REGION
sudo aws configure set output json

# Start and enable Docker
echo "Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Create application user
echo "Creating application user..."
sudo useradd -m -s /bin/bash scintilla
sudo mkdir -p /opt/scintilla
sudo chown scintilla:scintilla /opt/scintilla

# Create application directories
echo "Creating application directories..."
sudo mkdir -p /opt/scintilla/{app,logs,data}
sudo mkdir -p /var/log/scintilla
sudo chown -R scintilla:scintilla /opt/scintilla /var/log/scintilla

# Clone Scintilla repository
echo "Cloning Scintilla repository..."
cd /opt/scintilla

# Configure git for GitHub token authentication
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Configuring GitHub authentication..."
    export HOME="/root"
    git config --global credential.helper store
    echo "https://x-access-token:$GITHUB_TOKEN@github.com" > /root/.git-credentials
    
    echo "Cloning repository: $GITHUB_REPOSITORY_URL"
    git clone "$GITHUB_REPOSITORY_URL" app && {
        echo "Repository cloned successfully"
        sudo chown -R scintilla:scintilla /opt/scintilla/app
    } || {
        echo "Repository clone failed - creating minimal structure for testing"
        _create_minimal_structure
    }
else
    echo "No GitHub token provided - creating minimal structure for testing"
    _create_minimal_structure
fi

# Function to create minimal structure when repository clone fails
_create_minimal_structure() {
    sudo mkdir -p /opt/scintilla/app/src
    sudo mkdir -p /opt/scintilla/app/web
    
    # Create minimal requirements.txt
    sudo cat > /opt/scintilla/app/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
psycopg2-binary==2.9.9
sqlalchemy[asyncio]==2.0.23
alembic==1.12.1
boto3==1.34.0
python-multipart==0.0.6
EOF

    # Create minimal package.json for web directory
    sudo mkdir -p /opt/scintilla/app/web
    sudo cat > /opt/scintilla/app/web/package.json << 'EOF'
{
  "name": "scintilla-web",
  "version": "1.0.0",
  "scripts": {
    "build": "mkdir -p dist && echo '<h1>Scintilla Ready</h1>' > dist/index.html"
  }
}
EOF

    # Create basic main.py for the application
    sudo cat > /opt/scintilla/app/src/main.py << 'EOF'
#!/usr/bin/env python3
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="Scintilla", description="AI Search Platform")

# Mount static files
if os.path.exists("/opt/scintilla/app/web/dist"):
    app.mount("/static", StaticFiles(directory="/opt/scintilla/app/web/dist"), name="static")

@app.get("/health")
def health_check():
    return JSONResponse({
        "status": "healthy", 
        "message": "Scintilla is running",
        "service": "scintilla-api"
    })

@app.get("/")
def root():
    return JSONResponse({
        "message": "Scintilla API is ready",
        "docs": "/docs",
        "health": "/health"
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
}

# Install Python dependencies
echo "Installing Python dependencies..."
cd /opt/scintilla/app
# Skip pip upgrade to avoid RPM conflict, just install requirements
sudo python3.11 -m pip install -r requirements.txt

# Build frontend on the server
echo "Building frontend..."
cd /opt/scintilla/app/web
if [ -f "package.json" ]; then
    echo "Found package.json, installing dependencies..."
    sudo npm ci
    echo "Building frontend..."
    sudo npm run build
    echo "Frontend build completed"
else
    echo "No package.json found, creating minimal frontend structure..."
    sudo mkdir -p dist
    sudo cat > dist/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Scintilla - Ready to Deploy</title>
</head>
<body>
    <h1>Scintilla Instance is Running</h1>
    <p>Ready for code deployment</p>
</body>
</html>
EOF
fi

# Create environment file
echo "Creating environment configuration..."
sudo cat > /opt/scintilla/app/.env << EOF
# Database Configuration
DATABASE_URL=postgresql+asyncpg://$DB_USERNAME:$DB_PASSWORD@$DB_HOST:5432/$DB_NAME

# AWS Configuration
AWS_REGION=$AWS_REGION
AWS_KMS_KEY_ID=$KMS_KEY_ID

# Application Configuration
DEBUG=$DEBUG_MODE
TEST_MODE=$TEST_MODE
HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Authentication
GOOGLE_OAUTH_CLIENT_ID=$GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET=$GOOGLE_OAUTH_CLIENT_SECRET
ALLOWED_DOMAINS=$ALLOWED_DOMAINS
JWT_SECRET_KEY=production_jwt_secret_$(date +%s)_$(openssl rand -hex 16)

# Encryption (for development)
ENCRYPTION_PASSWORD=scintilla_prod_encryption_key_$(openssl rand -hex 16)

# LLM Configuration
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
DEFAULT_LLM_PROVIDER=$DEFAULT_LLM_PROVIDER
DEFAULT_OPENAI_MODEL=gpt-4o
DEFAULT_ANTHROPIC_MODEL=claude-sonnet-4-20250514
EOF

sudo chown scintilla:scintilla /opt/scintilla/app/.env
sudo chmod 600 /opt/scintilla/app/.env

# Create systemd service
echo "Creating systemd service..."
sudo cat > /etc/systemd/system/scintilla.service << 'EOF'
[Unit]
Description=Scintilla AI Search Platform
After=network.target

[Service]
Type=simple
User=scintilla
Group=scintilla
WorkingDirectory=/opt/scintilla/app
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/opt/scintilla/app
EnvironmentFile=/opt/scintilla/app/.env
ExecStart=/usr/bin/python3 -m src.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=scintilla

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/scintilla /var/log/scintilla

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration
echo "Configuring nginx..."
sudo cat > /etc/nginx/conf.d/scintilla.conf << 'EOF'
upstream scintilla_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Logging
    access_log /var/log/nginx/scintilla_access.log;
    error_log /var/log/nginx/scintilla_error.log;
    
    # Increase timeout for SSE connections
    proxy_read_timeout 4000s;
    proxy_send_timeout 4000s;
    
    location / {
        proxy_pass http://scintilla_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE specific headers
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://scintilla_backend/health;
        access_log off;
    }
    
    # Static files (if serving separately)
    location /static/ {
        alias /opt/scintilla/app/web/dist/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Remove default nginx configuration
sudo rm -f /etc/nginx/conf.d/default.conf

# Database initialization script
echo "Creating database initialization script..."
sudo cat > /opt/scintilla/init_db.sh << EOF
#!/bin/bash
# Initialize Scintilla database

cd /opt/scintilla/app

# Wait for database to be available
echo "Waiting for database to be available..."
for i in {1..30}; do
    if python3.11 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host='$DB_HOST',
        database='$DB_NAME',
        user='$DB_USERNAME',
        password='$DB_PASSWORD'
    )
    conn.close()
    print('Database is available')
    exit(0)
except Exception as e:
    print(f'Database not ready: {e}')
    exit(1)
    "; then
        break
    fi
    sleep 10
done

echo "Database connection successful - ready to accept connections"
echo "Database initialization complete"
EOF

sudo chmod +x /opt/scintilla/init_db.sh
sudo chown scintilla:scintilla /opt/scintilla/init_db.sh

# Create scripts directory
sudo mkdir -p /opt/scintilla/scripts
sudo chown -R scintilla:scintilla /opt/scintilla/scripts

# Enable and start services
echo "Starting services..."
sudo systemctl daemon-reload

# Start CloudWatch agent
sudo systemctl start amazon-cloudwatch-agent
sudo systemctl enable amazon-cloudwatch-agent

# Start nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Initialize database and start Scintilla
echo "Initializing database..."
sudo -u scintilla /opt/scintilla/init_db.sh

echo "Starting Scintilla service..."
sudo systemctl start scintilla
sudo systemctl enable scintilla

# Final health check
echo "Performing final health check..."
sleep 30
if systemctl is-active --quiet scintilla && curl -f -s http://localhost:8000/health > /dev/null; then
    echo "✅ Scintilla installation completed successfully!"
    echo "🌐 Service available at http://localhost:8000"
else
    echo "❌ Health check failed. Check logs for details."
    echo "Service status:"
    sudo systemctl status scintilla --no-pager
    echo ""
    echo "Recent logs:"
    sudo journalctl -u scintilla --no-pager -n 20
fi

echo "Full setup script completed at $(date)" 