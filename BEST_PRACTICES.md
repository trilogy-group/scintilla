# Scintilla Best Practices Guide

## Overview
This document outlines best practices for LLM application development based on industry research (2024-2025) and our implementation experience with Scintilla.

## 1. Vector Database Strategy

### Current Best Practices (2025)
Based on extensive research, the vector database landscape has matured significantly:

**For Enterprise RAG Applications:**
- **Qdrant** leads in performance (1.6-3.5ms latency, 1200+ QPS)
- **Weaviate** offers rich hybrid search capabilities
- **pgvector** provides 75% cost reduction vs proprietary solutions

**Key Considerations:**
- Hybrid search (vector + metadata) is now standard
- Multi-tenant isolation is crucial for SaaS
- Serverless architectures reduce operational overhead

### Our Implementation
Scintilla uses **PostgreSQL with custom caching** rather than a dedicated vector database because:
- Our primary use case is tool discovery, not semantic search
- We cache tool metadata, not embeddings
- PostgreSQL provides sufficient performance with proper indexing

**Future Consideration:** If we add semantic search over documents, consider Qdrant or pgvector for optimal performance.

## 2. Caching Strategies

### Industry Best Practices

**Three-Layer Caching Architecture:**
1. **Response Caching** - Cache complete LLM responses
2. **Embedding Caching** - Cache vector representations  
3. **KV Caching** - Cache transformer key-value states

**Semantic Caching Benefits:**
- 30-40% of LLM requests are semantically similar
- Can reduce costs by $80k+ quarterly for high-volume applications
- MeanCache achieves 17% higher F-score than exact-match caches

### Our Implementation

**Tool Metadata Caching:**
```python
# Global cache for tool metadata
async def refresh_tools_for_source(source: Source):
    tools = await fetch_from_mcp_server(source)
    await store_in_database(tools)
    source.tools_last_cached_at = datetime.now()
```

**Performance Impact:**
- 500x improvement (25s → 50ms)
- Eliminated redundant MCP server calls
- Database-backed for persistence

**Future Improvements:**
- Add semantic caching for similar queries
- Implement response caching for common questions
- Consider Redis for distributed caching

## 3. Server-Sent Events (SSE) Best Practices

### Industry Standards
SSE is preferred over WebSockets for unidirectional updates because:
- Simpler implementation (uses standard HTTP)
- Automatic reconnection built-in
- Lower overhead than WebSockets
- Works with standard load balancers

### Our Implementation

**FastAPI SSE Pattern:**
```python
async def stream_response():
    async for chunk in agent.astream():
        data = {
            "type": "content",
            "content": chunk,
            "metadata": {...}
        }
        yield f"data: {json.dumps(data)}\n\n"
```

**Key Features:**
- Structured event types (content, citation, error, done)
- Metadata in each event for context
- Clean error handling with try/finally

## 4. MCP (Model Context Protocol) Integration

### Best Practices
- **Connection Pooling:** Reuse MCP connections across requests
- **Lazy Loading:** Only connect when tools are needed
- **Error Recovery:** Implement exponential backoff for failures
- **Schema Validation:** Validate tool schemas before caching

### Our Implementation

**FastMCP Integration:**
```python
class FastMCPToolManager:
    def __init__(self):
        self.clients = {}  # Connection pool
        
    async def get_or_create_client(self, source_url):
        if source_url not in self.clients:
            self.clients[source_url] = await self._create_client(source_url)
        return self.clients[source_url]
```

## 5. LangChain Best Practices

### Tool Creation
**Use StructuredTool for proper schema handling:**
```python
# Good - handles parameters correctly
tool = StructuredTool(
    name=mcp_tool.name,
    description=mcp_tool.description,
    func=func_impl,
    args_schema=pydantic_model
)

# Bad - can cause "too many arguments" errors
tool = Tool(name=..., func=..., description=...)
```

### Agent Configuration
```python
agent = AgentExecutor(
    agent=agent,
    tools=tools,
    handle_parsing_errors=True,  # Important for robustness
    max_iterations=3,  # Prevent infinite loops
    return_intermediate_steps=True  # For debugging
)
```

## 6. Citation Extraction

### Best Practices
- Extract citations from tool outputs immediately
- Support multiple citation formats (JSON, markdown, plain text)
- Deduplicate citations across tool calls
- Preserve all sources when multiple are found

### Our Implementation
```python
class CitationManager:
    @staticmethod
    def extract_from_jira(content: str) -> List[Citation]:
        # Try JSON parsing first
        try:
            data = json.loads(content)
            if "issues" in data:
                return [extract_citation(issue) for issue in data["issues"]]
        except:
            # Fallback to regex
            return regex_extract_citations(content)
```

## 7. Performance Optimization

### Database Queries
- Use `selectinload` for eager loading relationships
- Extract model attributes before async operations
- Batch database operations where possible

### Async Best Practices
```python
# Good - extract attributes early
bot = await db.get(Bot, bot_id)
bot_name = bot.name  # Extract before any async operations
await db.flush()
# Use bot_name, not bot.name after flush
```

### Connection Management
- Use connection pooling for all external services
- Implement circuit breakers for failing services
- Set appropriate timeouts (30s for LLM, 5s for MCP)

## 8. Error Handling

### Structured Error Responses
```python
class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Graceful Degradation
- Continue with partial results if some sources fail
- Log errors but don't crash the request
- Provide clear error messages to users

## 9. Security Best Practices

### Credential Management
- Use AWS KMS for encryption at rest
- Rotate API keys regularly
- Never log sensitive credentials
- Use environment variables for secrets

### Input Validation
- Use Pydantic models for all API inputs
- Validate URLs before making requests
- Sanitize user inputs in prompts
- Implement rate limiting

## 10. Testing Strategy

### Unit Tests
- Mock external services (LLM, MCP servers)
- Test error conditions explicitly
- Use pytest fixtures for database setup

### Integration Tests
- Test with real MCP servers in staging
- Verify citation extraction with real data
- Test SSE streaming end-to-end

### Performance Tests
```python
async def test_concurrent_queries():
    # Test system under load
    tasks = [query_handler.handle_query(...) for _ in range(100)]
    results = await asyncio.gather(*tasks)
    assert all(r.success for r in results)
```

## Summary

The key to building successful LLM applications is:
1. **Cache aggressively** - Every layer should cache
2. **Stream responses** - Use SSE for better UX
3. **Handle errors gracefully** - Partial results are better than failures
4. **Optimize for the common case** - Most queries are similar
5. **Monitor everything** - Structured logging is essential

Following these practices has allowed Scintilla to achieve:
- Sub-second response times
- 500x performance improvement through caching
- Robust multi-source querying
- Clean, maintainable architecture 