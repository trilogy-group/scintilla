# Scintilla

IgniteTech's **search-focused** federated knowledge base tool. Query across multiple knowledge sources using intelligent LLM agents with MCP (Model Context Protocol) integration for comprehensive, read-only information discovery.

## 🔍 Key Features

- **🧠 Search-Focused Intelligence**: Specialized for deep knowledge base exploration
- **🚫 Read-Only Safety**: Automatic filtering of action tools to prevent accidental changes
- **🤖 Multi-LLM Support**: Choose between OpenAI (GPT-4) and Anthropic (Claude) models
- **🔧 MCP Integration**: Connects to Model Context Protocol servers for tool discovery
- **📚 Multi-Source Search**: Query across GitHub repositories, code, issues, and documentation
- **⚡ Real-time Streaming**: Server-Sent Events for live response streaming
- **🔐 Secure**: Google OAuth authentication with encrypted credential management
- **🌐 AWS Ready**: Designed for deployment on AWS with KMS encryption

## 🎯 Search Modes

### **Search Mode** (Thorough Knowledge Discovery)
- Deep exploration across multiple sources
- Minimum source requirements for comprehensive answers
- Cross-referencing between different knowledge bases
- Detailed citations and confidence indicators

### **Conversational Mode** (Interactive Assistance)
- Lighter, faster responses for quick questions
- Maintains context across conversation
- Balanced search depth for real-time interaction

## 🏗️ Architecture

- **Backend**: FastAPI with LangChain orchestration
- **Database**: PostgreSQL with JSONB for flexible data storage
- **Authentication**: Google OAuth 2.0 with domain validation
- **LLM Providers**: OpenAI and Anthropic support
- **MCP Protocol**: Real-time tool discovery and execution
- **AWS Services**: KMS for encryption, RDS, EC2, ALB
- **Search Engine**: Intelligent tool filtering and query encapsulation

### Database Schema

```
users
├── user_id (UUID)
├── google_sub, email, display_name
└── created_at, last_login

bots  
├── bot_id (UUID)
├── display_name, description
├── owner_email → users.email
└── is_active, is_public

bot_endpoints
├── endpoint_id (UUID)
├── bot_id → bots.bot_id
├── sse_url (base URL without API key)
├── api_key_encrypted (AES encrypted)
├── dek_encrypted (envelope encryption)
└── health status fields

conversations
├── conversation_id (UUID)
├── user_id → users.user_id
├── bot_id → bots.bot_id
├── llm_provider, llm_model
└── timestamps

messages
├── message_id (BigInt)
├── conversation_id → conversations
├── role, content
├── tool_calls, tool_results, citations (JSON)
└── llm metadata
```

### MCP URL Format

Scintilla supports MCP URLs with embedded API keys:

```
@https://mcp-server.ti.trilogy.com/0cf9bd44/sse?x-api-key=sk-hive-api01-...
```

The system automatically:
- Parses the base URL and API key separately  
- Encrypts the API key using AWS KMS envelope encryption
- Stores the base URL and encrypted key in separate database fields
- Reconstructs the full URL when making MCP calls

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Google OAuth credentials (for production)
- API keys for OpenAI and/or Anthropic

### Local Development

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd scintilla
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment setup**:
   Create a `.env` file using the template:
   ```bash
   cp env.template .env
   # Edit .env with your real API keys and configuration
   ```
   
   Required variables:
   ```bash
   # Database
   DATABASE_URL=postgresql://scintilla:scintilla_dev@localhost:5432/scintilla
   
   # LLM API Keys  
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   
   # AWS & Security
   AWS_KMS_KEY_ID=your_kms_key_id_here
   JWT_SECRET_KEY=your_jwt_secret_here
   
   # Application settings
   DEBUG=true
   DEFAULT_LLM_PROVIDER=anthropic
   ALLOWED_DOMAINS=ignitetech.com,ignitetech.ai
   ```

3. **Start local database**:
   ```bash
   docker-compose up -d postgres
   ```

4. **Initialize database**:
   ```bash
   python scripts/init_db.py
   ```

5. **Run the application**:
   ```bash
   python -m src.main
   ```

6. **Access the API**:
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## Configuration

Key environment variables:

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `DEFAULT_LLM_PROVIDER`: Default provider (`anthropic` or `openai`)
- `DATABASE_URL`: PostgreSQL connection string
- `ALLOWED_DOMAINS`: Comma-separated list of allowed email domains

## API Endpoints

### Core Endpoints

- `GET /health` - Health check
- `GET /` - API information  
- `POST /api/query` - Main search query endpoint with streaming response

### Search Query API

The main endpoint supports both search and conversational modes:

```bash
# Search Mode (Thorough Knowledge Discovery)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock_token_12345" \
  -d '{
    "message": "How does authentication work in our React applications?",
    "bot_ids": ["bot-uuid-here"],
    "mode": "search",
    "require_sources": true,
    "min_sources": 2,
    "search_depth": "thorough",
    "stream": true,
    "llm_provider": "anthropic",
    "llm_model": "claude-3-5-sonnet-20241022"
  }'

# Conversational Mode (Quick Responses)
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock_token_12345" \
  -d '{
    "message": "What are the latest GitHub activities?",
    "bot_ids": ["bot-uuid-here"],
    "mode": "conversational",
    "require_sources": false,
    "search_depth": "quick",
    "stream": false,
    "llm_provider": "anthropic"
  }'
```

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message` | string | required | User's search query |
| `bot_ids` | array | required | List of bot UUIDs to use |
| `mode` | string | "conversational" | "search" or "conversational" |
| `require_sources` | boolean | true | Require multiple sources |
| `min_sources` | integer | 2 | Minimum sources for search mode |
| `search_depth` | string | "thorough" | "quick", "thorough", "exhaustive" |
| `stream` | boolean | true | Enable streaming response |
| `llm_provider` | string | "anthropic" | "anthropic" or "openai" |
| `llm_model` | string | auto | Specific model to use |

## 🧪 Testing

Scintilla includes a comprehensive test suite to verify all functionality.

### Quick Test Run

```bash
# Run all tests
python tests/run_tests.py

# Run specific test categories
python tests/test_search_focused.py      # Core search functionality
python tests/test_endpoints.py           # API endpoints
python tests/test_real_hive_servers.py   # Real server integration
python tests/test_credential_system.py   # Security & credentials
```

### Manual API Testing

```bash
# General API testing
bash tests/test_curl_commands.sh

# Jira integration testing
bash tests/test_jira_curl.sh
```

### Test Categories

| Test Suite | Purpose | Key Validations |
|------------|---------|-----------------|
| **Search System** | Core search functionality | Tool filtering, query encapsulation, multi-source |
| **API Endpoints** | HTTP API validation | Health, streaming, non-streaming responses |
| **Real Servers** | Integration testing | Live MCP server connections, tool discovery |
| **Credentials** | Security testing | Encryption, storage, retrieval |

### Expected Results

When all tests pass, you'll see:
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

### Test Coverage

- ✅ **9+ search tools** properly filtered from 25+ total tools
- ✅ **Action tools excluded** (create, update, delete operations)
- ✅ **Multi-source search** with cross-referencing
- ✅ **Real-time streaming** with chunked responses
- ✅ **Credential encryption/decryption** with KMS
- ✅ **Multiple MCP servers** connected simultaneously

For detailed testing documentation, see [`tests/README.md`](tests/README.md).

## 💻 Development

### Project Structure

```
scintilla/
├── src/                 # Main application code
│   ├── main.py         # FastAPI app entry point
│   ├── config.py       # Configuration management
│   ├── api/            # FastAPI routes
│   │   ├── query.py    # Main search query endpoint
│   │   ├── models.py   # Request/response models
│   │   └── mcp_management.py # MCP server management
│   ├── agents/         # LangChain + MCP integration
│   │   └── langchain_mcp.py # Search-focused agent
│   ├── db/             # Database models & operations
│   │   ├── models.py   # SQLAlchemy models
│   │   └── encryption.py # KMS encryption utilities
│   └── auth/           # Authentication logic
├── tests/              # Comprehensive test suite
│   ├── run_tests.py    # Test runner
│   ├── test_search_focused.py # Core search tests
│   └── ...             # Additional test files
├── alembic/            # Database migrations
├── scripts/            # Utility scripts
└── requirements.txt    # Python dependencies
```

### Development Workflow

1. **Setup**: Follow the Quick Start guide above
2. **Code Changes**: Make changes in `src/`
3. **Test**: Run `python tests/run_tests.py` to verify
4. **Format**: Use `black src/` and `isort src/` for code formatting
5. **Database**: Use `alembic upgrade head` for schema changes

### Key Components

- **Search Agent** (`src/agents/langchain_mcp.py`): Core search intelligence with tool filtering
- **Query API** (`src/api/query.py`): Main endpoint with streaming support
- **MCP Integration**: Real-time tool discovery and execution
- **Credential Management**: Secure storage with KMS encryption

## Deployment

The application is designed for AWS deployment using:

- **Application Load Balancer** (4000s timeout for SSE)
- **EC2 Auto Scaling Group** 
- **RDS PostgreSQL** (Multi-AZ)
- **AWS KMS** (envelope encryption)

Infrastructure code will be provided in the `infra/` directory.

## License

Internal IgniteTech project. 