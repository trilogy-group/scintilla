# Scintilla

IgniteTech's **intelligent federated search and chat platform**. Connect to multiple knowledge sources through MCP (Model Context Protocol) servers, ask questions across your entire knowledge base, and get AI-powered responses with proper citations.

## 🚀 What is Scintilla?

Scintilla is a modern search-focused platform that:
- **🔍 Searches Multiple Sources**: Connect GitHub, Google Drive, Jira, documentation, and more
- **🧠 AI-Powered Responses**: Uses Claude Sonnet and GPT-4o for intelligent answers  
- **📚 Proper Citations**: All responses include source citations and links
- **⚡ High Performance**: Server-level tool caching for sub-second response times
- **🔐 Secure**: Google OAuth authentication with encrypted credential management
- **🤖 Bot Management**: Create specialized bots with curated knowledge sources

## 🏗️ Current Architecture

### Backend (FastAPI + Python)
- **FastAPI** application with structured logging
- **FastMCPAgent**: High-performance agent with database caching and FastMCP integration
- **PostgreSQL** database with tool caching and conversation history
- **AWS KMS** encryption for secure credential storage
- **Server-level tool caching** for 500x performance improvement

### Frontend (React + Vite)
- **Modern React SPA** with Tailwind CSS
- **Real-time streaming** responses via Server-Sent Events
- **Bot auto-complete** with intelligent suggestions
- **Source and Bot management** interfaces
- **Conversation history** with search functionality
- **Landing page** with integrated search experience

### Database Schema (Current)
```
users                    # Google OAuth users
sources                  # Individual MCP server connections  
  ├── tools_last_cached_at
  ├── tools_cache_status
  └── tools_cache_error
bots                     # Collections of sources with specific purposes
  ├── source_ids[]
  ├── is_public
  └── allowed_user_ids[]
user_bot_access          # User permissions for bots
mcp_credentials          # Encrypted API keys and tokens
conversations            # Chat history
messages                 # Individual chat messages with tool usage
source_tools             # Cached tool metadata for performance
```

## ⚡ Performance Optimizations

### Global Tool Caching (June 2025)
- **Problem Solved**: Eliminated 25+ second tool discovery on every request
- **Solution**: Server-level tool caching with lazy loading
- **Result**: 500x performance improvement (25s → 50ms tool access)

### Key Performance Features:
- **Connection Pooling**: Reuse MCP connections across requests
- **Background Operations**: Conversation saving doesn't block responses
- **Smart Content Processing**: Intelligent truncation with context awareness
- **Source Tool Caching**: Database-backed tool metadata cache

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI + Python 3.11+ | REST API with async support |
| **Database** | PostgreSQL + SQLAlchemy | Data persistence with JSONB fields |
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
python scripts/test_global_cache.py      # Cache performance validation
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
│   │   │   └── McpStatus.jsx   # MCP status monitoring
│   │   ├── hooks/              # React hooks
│   │   │   ├── useScintilla.js # Main application hook
│   │   │   └── useBotAutoComplete.jsx # Bot suggestions
│   │   └── services/
│   │       └── api.js          # API client
│   └── package.json            # Frontend dependencies
├── tests/                      # Test suite
├── scripts/                    # Utility scripts
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

## 📈 Performance Metrics

| Metric | Before Optimization | After Optimization | Improvement |
|--------|-------------------|-------------------|-------------|
| Tool Loading | 25+ seconds | 50ms | **500x faster** |
| First Response | 25+ seconds | ~1 second | **25x faster** |
| Concurrent Users | Limited (sequential) | Unlimited (cached) | **∞x better** |
| Memory Usage | High per-request | Low (shared cache) | **90% reduction** |

## 🚀 AWS Deployment Strategy

### Production Architecture Overview

Scintilla is designed for enterprise-scale deployment on AWS using modern cloud-native patterns:

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
├── RDS PostgreSQL (Multi-AZ)
├── AWS KMS (credential encryption)
└── CloudWatch (monitoring & logs)
```

### Infrastructure Components

| Component | Service | Purpose | Configuration |
|-----------|---------|---------|---------------|
| **Compute** | EC2 Auto Scaling Group | Application hosting | t3.medium (2-10 instances) |
| **Load Balancer** | Application Load Balancer | Traffic distribution | 4000s timeout for SSE |
| **Database** | RDS PostgreSQL | Data persistence | db.t3.micro → db.r5.large |
| **Caching** | In-memory (FastMCP) | Tool cache | Built-in application cache |
| **Security** | AWS KMS | Credential encryption | Envelope encryption |
| **Monitoring** | CloudWatch | Logs & metrics | Structured JSON logging |
| **DNS** | Route 53 | Domain management | Health checks enabled |
| **SSL/TLS** | ACM | Certificate management | Auto-renewal |

### AWS Deployment (EC2 with Terraform)

**Automated Deployment Script** (Recommended):
```bash
# Copy and customize configuration
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars

# Deploy to development
./infra/deploy.sh -e development

# Deploy to production (with dry run first)
./infra/deploy.sh -e production --dry-run
./infra/deploy.sh -e production
```

**Manual Terraform Deployment** (For advanced users):
```bash
cd infra/terraform
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

### Environment-Specific Configurations

#### Development Environment
- **Instance Type**: t3.micro (single instance)
- **Database**: db.t3.micro (single AZ)
- **SSL**: Self-signed certificates
- **Monitoring**: Basic CloudWatch
- **Cost**: ~$50-100/month

#### Staging Environment
- **Instance Type**: t3.small (2 instances)
- **Database**: db.t3.small (Multi-AZ)
- **SSL**: ACM certificates
- **Monitoring**: Enhanced CloudWatch
- **Cost**: ~$150-250/month

#### Production Environment
- **Instance Type**: t3.medium+ (3-10 instances)
- **Database**: db.r5.large+ (Multi-AZ)
- **SSL**: ACM certificates with auto-renewal
- **Monitoring**: Full observability stack
- **Cost**: ~$500-2000/month (depending on scale)

### Security Best Practices

#### Network Security
- **VPC**: Isolated network with public/private subnets
- **Security Groups**: Least-privilege access rules
- **NACLs**: Additional network-level protection
- **VPC Flow Logs**: Network traffic monitoring

#### Application Security
- **IAM Roles**: Service-specific permissions
- **KMS Encryption**: Envelope encryption for credentials
- **Secrets Manager**: Secure credential rotation
- **WAF**: Web application firewall protection

#### Data Security
- **RDS Encryption**: Encryption at rest and in transit
- **Backup Encryption**: Encrypted automated backups
- **Access Logging**: Comprehensive audit trails
- **Data Classification**: Sensitive data identification

### Monitoring & Observability

#### CloudWatch Integration
```bash
# Custom metrics for application performance
aws logs create-log-group --log-group-name /aws/scintilla/application
aws logs create-log-group --log-group-name /aws/scintilla/access

# Set up alarms for critical metrics
aws cloudwatch put-metric-alarm \
  --alarm-name "Scintilla-HighErrorRate" \
  --alarm-description "Error rate above threshold" \
  --metric-name ErrorRate \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 300 \
  --threshold 5.0 \
  --comparison-operator GreaterThanThreshold
```

#### Key Metrics to Monitor
- **Application**: Response time, error rates, throughput
- **Infrastructure**: CPU, memory, disk, network utilization
- **Database**: Connection count, query performance, storage
- **Business**: User engagement, query success rates, tool usage

### Deployment Automation

#### CI/CD Pipeline (GitHub Actions)
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
      - uses: actions/checkout@v3
      - name: Deploy to AWS
        run: |
          # Build and test
          python -m pytest
          npm run build
          # Deploy infrastructure
          terraform apply -auto-approve
          # Deploy application
          aws ecs update-service --force-new-deployment
```

#### Blue-Green Deployment
```bash
# Create new target group
aws elbv2 create-target-group --name scintilla-green
# Deploy new version to green environment
# Health check validation
# Switch traffic from blue to green
aws elbv2 modify-listener --listener-arn $LISTENER_ARN --default-actions TargetGroupArn=$GREEN_TG
```

### Scaling Strategy

#### Auto Scaling Configuration
- **Target Tracking**: Scale based on CPU/memory utilization
- **Predictive Scaling**: Scale ahead of predicted demand
- **Custom Metrics**: Scale based on query volume or response time

#### Database Scaling
- **Read Replicas**: Distribute read traffic
- **Connection Pooling**: Optimize database connections
- **Query Optimization**: Regular performance tuning

### Disaster Recovery

#### Backup Strategy
- **RDS Automated Backups**: 7-day retention
- **Application Data**: S3 cross-region replication
- **Infrastructure**: Versioned IaC in source control

#### Recovery Procedures
- **RTO**: 4 hours (Recovery Time Objective)
- **RPO**: 1 hour (Recovery Point Objective)
- **Multi-AZ**: Automatic failover for database
- **Cross-Region**: Disaster recovery in secondary region

### Cost Optimization

#### Reserved Instances
- **EC2**: 1-3 year commitments for predictable workloads
- **RDS**: Reserved instances for database
- **Savings Plans**: Flexible compute pricing

#### Right-Sizing
- **Instance Monitoring**: Regular review of resource utilization
- **Auto Scaling**: Automatic adjustment to demand
- **Spot Instances**: Cost savings for non-critical workloads

### Compliance & Governance

#### Regulatory Compliance
- **SOC 2**: Security and availability controls
- **GDPR**: Data protection and privacy
- **HIPAA**: Healthcare data protection (if applicable)

#### Governance Framework
- **Tagging Strategy**: Consistent resource tagging
- **Cost Allocation**: Department/project cost tracking
- **Access Control**: Role-based access management

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

- [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md) - **Complete AWS deployment guide** with step-by-step instructions, architecture diagrams, and troubleshooting
- [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md) - **Production deployment checklist** with comprehensive verification steps
- [`PERFORMANCE_IMPROVEMENTS.md`](PERFORMANCE_IMPROVEMENTS.md) - Detailed performance optimization documentation
- [`BEST_PRACTICES.md`](BEST_PRACTICES.md) - Industry best practices guide covering vector databases, LLM integration, and deployment strategies
- [`CLEANUP_LOG.md`](CLEANUP_LOG.md) - Comprehensive record of codebase cleanup activities
- [`tests/README.md`](tests/README.md) - Testing documentation and guides
- [`web/README.md`](web/README.md) - Frontend-specific documentation

## 🤝 Contributing

1. Follow the existing code style and conventions
2. Run the full test suite before submitting changes
3. Update documentation for new features
4. Use structured logging for observability

## 📄 License

Internal IgniteTech project. 