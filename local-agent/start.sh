#!/bin/bash

# Scintilla Local Agent Startup Script

echo "🚀 Starting Scintilla Local Agent..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed or not in PATH"
    exit 1
fi

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if Docker is running
if ! docker version &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if configuration files exist
if [ ! -f "config.yaml" ]; then
    echo "❌ config.yaml not found. Please create one based on the template."
    exit 1
fi

if [ ! -f "mcp_servers.yaml" ]; then
    echo "❌ mcp_servers.yaml not found. Please create one based on the template."
    exit 1
fi

# Install dependencies if requirements.txt exists and venv is not active
if [ ! -z "${VIRTUAL_ENV}" ]; then
    echo "✅ Virtual environment detected: ${VIRTUAL_ENV}"
elif [ -f "requirements.txt" ]; then
    echo "⚠️  No virtual environment detected. Installing requirements globally..."
    pip3 install -r requirements.txt
fi

# Check if dependencies are installed
echo "🔍 Checking dependencies..."
python3 -c "import aiohttp, yaml, pydantic" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencies not installed. Run: pip install -r requirements.txt"
    exit 1
fi

echo "✅ All checks passed!"
echo ""

# Run the agent
echo "🤖 Starting local agent..."
python3 agent.py

echo "🛑 Local agent stopped." 