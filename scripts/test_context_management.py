#!/usr/bin/env python3
"""
Test Context Management System

Tests token estimation, conversation truncation, and context optimization.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.context_manager import ContextManager, TokenEstimator, ModelLimits
from langchain_core.messages import HumanMessage, AIMessage

def test_token_estimation():
    """Test token estimation"""
    print("=== Testing Token Estimation ===")
    
    # Test basic text
    text1 = "Hello, how are you today?"
    tokens1 = TokenEstimator.estimate_tokens(text1)
    print(f"Text: '{text1}' → {tokens1} tokens (~{len(text1)/tokens1:.1f} chars/token)")
    
    # Test longer text
    text2 = "This is a much longer piece of text that should have more tokens. " * 10
    tokens2 = TokenEstimator.estimate_tokens(text2)
    print(f"Long text: {len(text2)} chars → {tokens2} tokens (~{len(text2)/tokens2:.1f} chars/token)")
    
    # Test message tokens
    msg_tokens = TokenEstimator.estimate_message_tokens("user", text1)
    print(f"Message tokens (includes role overhead): {msg_tokens}")

def test_model_limits():
    """Test model limit detection"""
    print("\n=== Testing Model Limits ===")
    
    models = [
        "claude-3-5-sonnet-20241022",
        "gpt-4o-mini",
        "gpt-4",
        "unknown-model-xyz"
    ]
    
    for model in models:
        limits = ModelLimits.get_limits(model)
        print(f"{model}: {limits.context_window:,} window, {limits.safe_limit:,} safe limit")

def test_conversation_truncation():
    """Test conversation history truncation"""
    print("\n=== Testing Conversation Truncation ===")
    
    # Create context manager for GPT-4 (smaller context for testing)
    context_manager = ContextManager("gpt-4")
    
    # Create long conversation history
    conversation = []
    for i in range(20):
        conversation.append(HumanMessage(content=f"This is user message {i+1}. " * 50))
        conversation.append(AIMessage(content=f"This is assistant response {i+1}. " * 50))
    
    print(f"Original conversation: {len(conversation)} messages")
    
    # Estimate tokens
    total_tokens = 0
    for msg in conversation:
        role = "user" if "Human" in str(type(msg)) else "assistant"
        tokens = TokenEstimator.estimate_message_tokens(role, msg.content)
        total_tokens += tokens
    
    print(f"Original conversation tokens: ~{total_tokens}")
    
    # Truncate with different reserved token amounts
    for reserved in [1000, 3000, 5000]:
        truncated = context_manager.truncate_conversation_history(conversation, reserved)
        print(f"Reserved {reserved} tokens → kept {len(truncated)} messages")

def test_tool_result_truncation():
    """Test tool result truncation"""
    print("\n=== Testing Tool Result Truncation ===")
    
    context_manager = ContextManager("claude-3-5-sonnet-20241022")
    
    # Create large tool result
    large_result = "This is a very large tool result. " * 1000
    print(f"Original result: {len(large_result)} chars")
    
    # Test different max token limits
    for max_tokens in [1000, 2000, 5000]:
        truncated = context_manager.truncate_tool_result(large_result, max_tokens)
        print(f"Max {max_tokens} tokens → {len(truncated)} chars")
        
        # Show truncation pattern
        if len(truncated) < len(large_result):
            if "TRUNCATED" in truncated:
                parts = truncated.split("[... TRUNCATED:")
                start_len = len(parts[0])
                end_part = parts[1].split("...]\n\n")[-1]
                end_len = len(end_part)
                print(f"  Kept: {start_len} chars from start + {end_len} chars from end")

def test_context_optimization():
    """Test full context optimization"""
    print("\n=== Testing Context Optimization ===")
    
    context_manager = ContextManager("gpt-4")  # Smaller context for testing
    
    # Create test data
    system_prompt = "You are a helpful assistant. " * 100  # Large system prompt
    conversation = []
    for i in range(15):
        conversation.append(HumanMessage(content=f"Question {i+1}: " + "What can you tell me about this topic? " * 20))
        conversation.append(AIMessage(content=f"Answer {i+1}: " + "Here's what I know about that. " * 30))
    
    current_message = "Tell me everything about the latest developments."
    tool_results = ["Tool result 1: " + "Large data response. " * 200, 
                   "Tool result 2: " + "Another large response. " * 200]
    citation_context = "Available sources: " + "Source information. " * 100
    
    # Check if optimization is needed
    is_safe, current_tokens, limit = context_manager.check_context_safety(
        system_prompt=system_prompt,
        conversation_history=conversation,
        current_message=current_message,
        tool_results=tool_results,
        citation_context=citation_context
    )
    
    print(f"Before optimization: {current_tokens:,} tokens (safe: {is_safe}, limit: {limit:,})")
    
    # Optimize
    optimized_history, optimized_tools, optimized_citation = context_manager.optimize_context(
        system_prompt=system_prompt,
        conversation_history=conversation,
        current_message=current_message,
        tool_results=tool_results,
        citation_context=citation_context
    )
    
    # Check after optimization
    is_safe_after, tokens_after, _ = context_manager.check_context_safety(
        system_prompt=system_prompt,
        conversation_history=optimized_history,
        current_message=current_message,
        tool_results=optimized_tools,
        citation_context=optimized_citation
    )
    
    print(f"After optimization: {tokens_after:,} tokens (safe: {is_safe_after})")
    print(f"Conversation: {len(conversation)} → {len(optimized_history)} messages")
    print(f"Tool results: {len(tool_results)} → {len(optimized_tools)} results")
    print(f"Citation context: {len(citation_context)} → {len(optimized_citation)} chars")

def main():
    """Run all tests"""
    print("🧪 Testing Scintilla Context Management System\n")
    
    test_token_estimation()
    test_model_limits()
    test_conversation_truncation()
    test_tool_result_truncation()
    test_context_optimization()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main() 