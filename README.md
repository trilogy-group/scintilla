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
- **Dual Agent System**: 
  - `FastMCPAgent`: Performance-optimized with database caching
  - `MCPAgent`: Full-featured agent with comprehensive tool execution
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
│   │   ├── fast_agent.py       # Performance-optimized agent
│   │   ├── langchain_mcp.py    # Full-featured MCP agent
│   │   ├── mcp_loader.py       # MCP configuration utilities
│   │   ├── mcp_client.py       # Direct MCP client implementation
│   │   └── citations.py        # Source citation management
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

## 🚧 Known Areas for Cleanup

Based on code investigation, the following areas need attention:

### Test Code in Source
- `src/utils/url_parser.py` lines 186-209: Contains test code that should be moved to `tests/`

### TODO Items
- Multiple TODO comments throughout the codebase for permission checks
- Missing real-time connection testing for sources
- Incomplete tool count tracking from MCP clients

### Potential Refactoring
- Some debugging utilities could be consolidated in `scripts/`
- Legacy MCP server configurations could be simplified

## 🔒 Security Features

- **Google OAuth 2.0** with domain restriction (@ignitetech.com, @ignitetech.ai)
- **AWS KMS envelope encryption** for API keys and credentials
- **Connection security** with HTTPS-only MCP connections
- **Input validation** with Pydantic models
- **SQL injection protection** with SQLAlchemy ORM

## 🚀 Deployment

### AWS Architecture
- **Application Load Balancer** with 4000s timeout for SSE
- **EC2 Auto Scaling Group** for application servers  
- **RDS PostgreSQL** with Multi-AZ for high availability
- **AWS KMS** for credential encryption

### Environment-Specific Configurations
- **Development**: Local PostgreSQL, mock authentication
- **Production**: AWS RDS, Google OAuth, KMS encryption

## 📊 Monitoring & Observability

- **Structured logging** with JSON output
- **Health check endpoints** with detailed MCP status
- **Performance metrics** tracking in logs
- **Error tracking** with detailed stack traces

## 📚 Additional Documentation

- [`PERFORMANCE_IMPROVEMENTS.md`](PERFORMANCE_IMPROVEMENTS.md) - Detailed performance optimization documentation
- [`tests/README.md`](tests/README.md) - Testing documentation and guides
- [`web/README.md`](web/README.md) - Frontend-specific documentation

## 🤝 Contributing

1. Follow the existing code style and conventions
2. Run the full test suite before submitting changes
3. Update documentation for new features
4. Use structured logging for observability

## 📄 License

Internal IgniteTech project. 