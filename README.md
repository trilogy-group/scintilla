# Scintilla - IgniteTech's Federated Search & Chat Tool

**Smart search across all your tools and knowledge bases** - Scintilla connects to MCP (Model Context Protocol) servers and uses AI to provide intelligent, cited answers from your connected sources.

## 🌟 Key Features

- **🔍 Federated Search**: Query across multiple MCP sources simultaneously
- **🤖 AI-Powered Chat**: LangChain agents with Anthropic Claude and OpenAI GPT
- **📊 Source Management**: Add, configure, and manage MCP tool sources
- **🎯 Bot Configuration**: Create specialized bots with custom instructions and source access
- **📝 Citation Tracking**: Every answer includes proper source citations
- **⚡ High Performance**: Tool caching for faster responses
- **🔐 Enterprise Security**: Google OAuth with domain restrictions and KMS encryption
- **📱 Modern UI**: React-based interface with real-time streaming responses

## 🏗️ Architecture Overview

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI + Python 3.11 | Async API with SSE streaming |
| **Database** | PostgreSQL + SQLAlchemy | Data persistence with async support |
| **LLM Integration** | LangChain + MCP Adapters | Tool orchestration and execution |
| **LLM Providers** | Anthropic Claude + OpenAI GPT | AI response generation |
| **Frontend** | React 19 + Vite + Tailwind | Modern SPA with real-time updates |
| **Authentication** | Google OAuth 2.0 | Secure user authentication |
| **Encryption** | AWS KMS + AES | Credential protection |
| **Deployment** | AWS (EC2, RDS, ALB) | Scalable cloud infrastructure |

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Docker (optional, for local database)

### 1. Backend Setup
```bash
# Clone and setup Python environment
git clone <repository-url>
cd scintilla
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment configuration
cp env.template .env
# Edit .env with your configuration
```

### 2. Database Setup
```bash
# Option A: Docker (recommended for development)
docker-compose up -d postgres

# Option B: Local PostgreSQL
# Ensure PostgreSQL is running and create database

# Initialize database
python scripts/init_db.py
```

### 3. Frontend Setup
```bash
cd web
npm install
npm run build  # For production builds
```

### 4. Run the Application
```bash
# Backend (from root directory)
python -m src.main

# Frontend development server (optional)
cd web && npm run dev
```

### 5. Access the Application
- **Main App**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📋 Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/scintilla

# LLM API Keys
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
DEFAULT_LLM_PROVIDER=anthropic

# AWS (for production)
AWS_REGION=us-east-1
AWS_KMS_KEY_ID=your_kms_key_id

# Authentication
GOOGLE_OAUTH_CLIENT_ID=your_google_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_google_client_secret
ALLOWED_DOMAINS=ignitetech.com,ignitetech.ai

# Application
DEBUG=true
TEST_MODE=false  # Set to true for development without MCP
```

## 🔧 API Endpoints

### Core Endpoints
- `GET /health` - System health with MCP status
- `POST /api/query` - Main search query with streaming
- `GET /api/conversations` - Conversation history
- `POST /api/conversations` - Create new conversation

### Management Endpoints
- `GET /api/sources` - List MCP sources
- `POST /api/sources` - Create new source
- `GET /api/bots` - List available bots
- `POST /api/bots` - Create new bot

### Query API Example
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock_token_12345" \
  -d '{
    "message": "How does authentication work in our React applications?",
    "bot_ids": ["bot-uuid-here"],
    "mode": "conversational",
    "stream": true,
    "llm_provider": "anthropic"
  }'
```

## 🧪 Testing

### Run Full Test Suite
```bash
python tests/run_tests.py
```

### Individual Test Categories
```bash
python tests/test_search_focused.py      # Core search functionality
python tests/test_endpoints.py           # API endpoint validation
python tests/test_real_hive_servers.py   # Live MCP integration
python tests/test_credential_system.py   # Security testing
```

### Performance Testing
```bash
python scripts/performance_test.py       # Comprehensive performance tests
python scripts/simple_test.py            # Basic functionality validation
```

## 📁 Project Structure

```
scintilla/
├── src/                        # Backend application code
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── api/                    # REST API endpoints
│   │   ├── query.py            # Main search endpoint
│   │   ├── query_handlers.py   # Query processing logic
│   │   ├── conversation_manager.py # Chat history management
│   │   ├── bots.py             # Bot management
│   │   ├── sources.py          # Source management
│   │   └── models.py           # Pydantic request/response models
│   ├── agents/                 # AI agent implementations
│   │   ├── fast_agent.py       # High-performance LangChain agent
│   │   ├── fast_mcp.py         # FastMCP tool management with caching
│   │   └── citations.py        # Source citation extraction
│   ├── db/                     # Database layer
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── tool_cache.py       # Tool caching service
│   │   ├── mcp_credentials.py  # Credential management
│   │   └── encryption.py       # Encryption utilities
│   └── auth/                   # Authentication
│       └── mock.py             # Development authentication
├── web/                        # Frontend React application
│   ├── src/
│   │   ├── App.jsx             # Main application component
│   │   ├── components/         # React components
│   │   │   ├── LandingPage.jsx # Landing page with search
│   │   │   ├── BotsManager.jsx # Bot management interface
│   │   │   ├── SourcesManager.jsx # Source management
│   │   │   ├── CitationRenderer.jsx # Citation display
│   │   │   └── GoogleAuth.jsx  # Authentication component
│   │   ├── hooks/              # React hooks
│   │   │   ├── useScintilla.js # Main application hook
│   │   │   └── useBotAutoComplete.jsx # Bot suggestions
│   │   └── services/
│   │       └── api.js          # API client
│   └── package.json            # Frontend dependencies
├── tests/                      # Test suite
├── scripts/                    # Utility scripts
│   ├── init_db.py              # Database initialization
│   ├── performance_test.py     # Performance benchmarking
│   ├── simple_test.py          # Basic functionality tests
│   ├── diagnose_tools.py       # Tool debugging utilities
│   ├── recache_tools.py        # Tool cache management
│   └── check_dependencies.py   # Dependency verification
├── alembic/                    # Database migrations
├── infra/                      # Infrastructure as Code
│   └── terraform/              # Terraform configurations for AWS EC2 deployment
└── requirements.txt            # Python dependencies
```

## 🔧 Development Workflow

### Code Quality
```bash
# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Run linting
flake8 src/
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Frontend Development
```bash
cd web
npm run dev     # Development server with hot reload
npm run build   # Production build
npm run lint    # ESLint checking
```


## 🚀 AWS Deployment

### Basic Production Architecture

```
Internet Gateway
       ↓
Application Load Balancer (ALB)
       ↓
Auto Scaling Group (EC2 instances)
       ↓
├── FastAPI Application (Port 8000)
├── React Frontend (served by FastAPI)
└── Health Check Endpoints
       ↓
├── RDS PostgreSQL
├── AWS KMS (credential encryption)
└── CloudWatch (basic monitoring)
```

### Infrastructure Components

| Component | Service | Configuration |
|-----------|---------|---------------|
| **Compute** | EC2 Auto Scaling Group | t3.micro to t3.medium |
| **Load Balancer** | Application Load Balancer | 4000s timeout for SSE |
| **Database** | RDS PostgreSQL | db.t3.micro to db.r5.large |
| **Security** | AWS KMS | Envelope encryption |
| **Monitoring** | CloudWatch | Basic logs & CPU alarms |

### Quick Deployment

```bash
# Copy and customize configuration
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars

# Deploy to development
./infra/deploy.sh -e development

# Deploy to production (with dry run first)
./infra/deploy.sh -e production --dry-run
./infra/deploy.sh -e production
```

### Environment Configurations

| Environment | Instance Type | Database | Estimated Cost |
|-------------|---------------|----------|----------------|
| **Development** | t3.micro (1 instance) | db.t3.micro | ~$50-100/month |
| **Staging** | t3.small (2 instances) | db.t3.small | ~$150-250/month |
| **Production** | t3.medium+ (3-10 instances) | db.r5.large+ | ~$500-1000/month |

### Basic Security Features

- **VPC**: Isolated network with public/private subnets
- **Security Groups**: Least-privilege access rules
- **KMS Encryption**: Envelope encryption for credentials
- **RDS Encryption**: Encryption at rest and in transit
- **Automated Backups**: 7-day retention configured

### Basic Monitoring

- **CloudWatch Logs**: Application and access logs
- **CPU Alarms**: Auto-scaling triggers
- **Health Checks**: Load balancer health monitoring
- **Application Metrics**: Response times and error rates

## 🔒 Security Features

- **Google OAuth 2.0** with domain restriction (@ignitetech.com, @ignitetech.ai)
- **AWS KMS envelope encryption** for API keys and credentials
- **Connection security** with HTTPS-only MCP connections
- **Input validation** with Pydantic models
- **SQL injection protection** with SQLAlchemy ORM

## 📊 Monitoring & Observability

- **Structured logging** with JSON output
- **Health check endpoints** with detailed MCP status
- **Performance metrics** tracking in logs
- **Error tracking** with detailed stack traces

## 📚 Additional Documentation

- [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md) - **Complete AWS deployment guide** with step-by-step instructions and troubleshooting
- [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md) - **Production deployment checklist** with verification steps
- [`PERFORMANCE_IMPROVEMENTS.md`](PERFORMANCE_IMPROVEMENTS.md) - Detailed performance optimization documentation
- [`BEST_PRACTICES.md`](BEST_PRACTICES.md) - Development and deployment best practices
- [`CLEANUP_LOG.md`](CLEANUP_LOG.md) - Record of codebase cleanup activities
- [`tests/README.md`](tests/README.md) - Testing documentation and guides
- [`web/README.md`](web/README.md) - Frontend-specific documentation

## 🤝 Contributing

1. Follow the existing code style and conventions
2. Run the full test suite before submitting changes
3. Update documentation for new features
4. Use structured logging for observability

## 📄 License

Internal IgniteTech project. 