#!/bin/bash
#
# Test Jira ticket creation with curl
#

BASE_URL="http://localhost:8000"
BOT_ID="0225c5f8-6f24-460d-8efc-da1e7266014c"

echo "🎫 Testing Jira Ticket Creation with Curl"
echo "=========================================="
echo "Project: https://ignitetechpm.atlassian.net/browse/AFSE" 
echo "Task: Parallel ticket processing"
echo ""

echo "📤 Sending request..."
curl -X POST "$BASE_URL/api/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock_token_12345" \
  -d '{
    "message": "Please create a jira ticket in https://ignitetechpm.atlassian.net/browse/AFSE project to handle parallel ticket processing. Proceed with creating the ticket now without asking for confirmation. Use these details: Title: '\''Implement Parallel Ticket Processing System'\'', Type: Feature, Priority: High, Description should include technical requirements and implementation approach.",
    "bot_ids": ["'$BOT_ID'"],
    "stream": false,
    "llm_provider": "anthropic",
    "llm_model": "claude-3-5-sonnet-20241022"
  }' | jq -r '.content'

echo ""
echo "✅ Jira ticket creation test completed!" 