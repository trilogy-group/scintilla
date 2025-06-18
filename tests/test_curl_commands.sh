#!/bin/bash
#
# Manual curl tests for Scintilla API endpoints
#

BASE_URL="http://localhost:8000"
BOT_ID="0225c5f8-6f24-460d-8efc-da1e7266014c"

echo "🚀 Manual Scintilla API Tests"
echo "=============================="

echo ""
echo "1️⃣ Testing Health Endpoint"
echo "curl -X GET $BASE_URL/health"
curl -X GET "$BASE_URL/health" | jq .
echo ""

echo ""
echo "2️⃣ Testing Non-Streaming Query"
echo "curl -X POST $BASE_URL/api/query"
curl -X POST "$BASE_URL/api/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock_token_12345" \
  -d '{
    "message": "What tools can you help me with?",
    "bot_ids": ["'$BOT_ID'"],
    "stream": false,
    "llm_provider": "anthropic",
    "llm_model": "claude-3-5-sonnet-20241022"
  }' | jq .
echo ""

echo ""
echo "3️⃣ Testing Streaming Query (first 10 lines)"
echo "curl -X POST $BASE_URL/api/query (streaming)"
curl -X POST "$BASE_URL/api/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock_token_12345" \
  -d '{
    "message": "Tell me about your GitHub tools",
    "bot_ids": ["'$BOT_ID'"],
    "stream": true,
    "llm_provider": "anthropic",
    "llm_model": "claude-3-5-sonnet-20241022"
  }' | head -10
echo ""

echo ""
echo "4️⃣ Testing API Documentation"
echo "Open in browser: $BASE_URL/docs"
echo ""

echo "✅ All manual tests completed!"
echo "💡 Tip: Visit $BASE_URL/docs for interactive API documentation" 