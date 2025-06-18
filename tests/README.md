# Scintilla Test Suite

Comprehensive testing framework for the Scintilla MCP knowledge search system.

## 🚀 Quick Start

### Run All Tests
```bash
# From project root
python tests/run_tests.py
```

### Run Individual Tests
```bash
# Core search functionality
python tests/test_search_focused.py

# API endpoints
python tests/test_endpoints.py

# Real server integration
python tests/test_real_hive_servers.py

# Credential management
python tests/test_credential_system.py
```

### Manual API Testing
```bash
# General API testing with curl
bash tests/test_curl_commands.sh

# Jira-specific testing
bash tests/test_jira_curl.sh
```

## 📋 Test Files Overview

### 🎯 Core Tests

| Test File | Purpose | What It Tests |
|-----------|---------|---------------|
| `test_search_focused.py` | **Primary system test** | Search modes, tool filtering, query encapsulation |
| `test_endpoints.py` | API functionality | Health, streaming, non-streaming endpoints |
| `test_real_hive_servers.py` | Integration testing | Real IgniteTech Hive server connections |
| `test_credential_system.py` | Security testing | Credential storage, encryption, retrieval |

### 🛠️ Manual Tests

| Test File | Purpose | Usage |
|-----------|---------|-------|
| `test_curl_commands.sh` | Manual API testing | Direct curl commands for debugging |
| `test_jira_curl.sh` | Jira integration | Test Jira ticket creation workflow |

### 🏃‍♂️ Test Runner

| File | Purpose |
|------|---------|
| `run_tests.py` | Comprehensive test runner with detailed reporting |

## 🔍 Test Categories

### **1. Search System Tests** (`test_search_focused.py`)
Tests the core knowledge base search functionality:
- ✅ **Search Mode**: Deep, thorough knowledge base exploration
- ✅ **Conversational Mode**: Lighter, interactive responses  
- ✅ **Tool Filtering**: Automatic exclusion of action tools
- ✅ **Query Encapsulation**: Intelligent search instruction wrapping
- ✅ **Multi-source Requirements**: Cross-referencing between sources

### **2. API Endpoint Tests** (`test_endpoints.py`)
Validates all API endpoints:
- ✅ **Health Check**: `/health` endpoint functionality
- ✅ **API Documentation**: `/docs` endpoint accessibility
- ✅ **Streaming Queries**: Real-time response streaming
- ✅ **Non-streaming Queries**: Standard JSON responses
- ✅ **Tool Loading**: MCP tool discovery and loading

### **3. Real Server Integration** (`test_real_hive_servers.py`)
Tests integration with actual IgniteTech Hive servers:
- ✅ **Multiple Servers**: Both AISE and GitHub servers
- ✅ **Tool Discovery**: 25+ tools from real servers
- ✅ **Credential Management**: Secure API key handling
- ✅ **Response Generation**: End-to-end query processing

### **4. Credential System** (`test_credential_system.py`)
Validates security and credential management:
- ✅ **Encryption**: KMS envelope encryption
- ✅ **Storage**: Secure database storage
- ✅ **Retrieval**: Decryption and usage
- ✅ **Error Handling**: Invalid credential scenarios

## 🎯 Expected Results

### ✅ All Tests Passing
When everything works correctly, you should see:
```
🎯 COMPREHENSIVE TEST SUMMARY
============================================================
search_system       : ✅ PASS
endpoints           : ✅ PASS  
real_servers        : ✅ PASS
credentials         : ✅ PASS

📊 Overall Results: 4/4 tests passed
🎉 ALL TESTS PASSED! Scintilla system is working perfectly!
```

### Key Metrics Verified:
- **🔧 9+ search tools** filtered from 25+ total tools
- **🚫 8+ action tools** properly excluded
- **📡 Streaming responses** with real-time chunks
- **🔐 Credential encryption/decryption** working
- **🌐 Multiple MCP servers** connected and functional

## 🔧 Prerequisites

### Environment Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.template .env
# Edit .env with your API keys and database URL
```

### Required Environment Variables
```bash
ANTHROPIC_API_KEY=your_key_here
DATABASE_URL=your_postgres_url
KMS_KEY_ID=your_kms_key_id
```

### Server Requirements
- **Scintilla server running** on `http://localhost:8000`
- **Database initialized** with Alembic migrations
- **MCP servers accessible** (IgniteTech Hive servers)

## 🐛 Troubleshooting

### Common Issues

#### ❌ Server Not Running
```
❌ Health check error: Cannot connect to host localhost:8000
```
**Solution**: Start the server first:
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

#### ❌ Missing Environment Variables
```
❌ ANTHROPIC_API_KEY environment variable is not set
```
**Solution**: Check your `.env` file and ensure all required variables are set.

#### ❌ Database Connection Issues
```
❌ Database connection failed
```
**Solution**: 
1. Check `DATABASE_URL` in `.env`
2. Run database migrations: `alembic upgrade head`
3. Ensure PostgreSQL is running

#### ❌ MCP Server Connection Issues
```
❌ No MCP tools available
```
**Solution**:
1. Verify IgniteTech Hive server URLs are accessible
2. Check API key validity
3. Ensure credential system is properly configured

## 📊 Performance Expectations

### Response Times
- **Health Check**: < 100ms
- **Tool Loading**: < 2 seconds for 25+ tools
- **Search Queries**: 2-5 seconds for comprehensive results
- **Streaming**: First chunk within 1 second

### Resource Usage
- **Memory**: ~200MB for full system
- **CPU**: Low usage during idle, moderate during queries
- **Network**: Dependent on MCP server response times

## 🚀 CI/CD Integration

### GitHub Actions Example
```yaml
name: Scintilla Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python tests/run_tests.py
```

## 📚 Additional Resources

- **Main README**: `../README.md` - Project overview and setup
- **API Documentation**: `http://localhost:8000/docs` - Interactive API docs
- **Source Code**: `../src/` - Implementation details
- **Configuration**: `../env.template` - Environment setup guide 