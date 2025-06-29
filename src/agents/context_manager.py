"""
Context Size Management for Scintilla

Handles token counting, conversation history truncation, and context window management
to prevent LLM context overflow.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

@dataclass
class ModelLimits:
    """Token limits for different LLM models"""
    context_window: int
    safe_limit: int  # Leave some buffer for response
    
    @classmethod
    def get_limits(cls, model_name: str) -> 'ModelLimits':
        """Get token limits for specific model"""
        
        # Claude models
        if "claude-3-5-sonnet" in model_name or "claude-sonnet-4" in model_name:
            return cls(context_window=200000, safe_limit=180000)
        elif "claude-3-haiku" in model_name:
            return cls(context_window=200000, safe_limit=180000)
        elif "claude-3-opus" in model_name:
            return cls(context_window=200000, safe_limit=180000)
        
        # OpenAI models
        elif "gpt-4o" in model_name:
            return cls(context_window=128000, safe_limit=120000)
        elif "gpt-4-turbo" in model_name:
            return cls(context_window=128000, safe_limit=120000)
        elif "gpt-4" in model_name:
            return cls(context_window=8192, safe_limit=7000)
        elif "gpt-3.5-turbo" in model_name:
            return cls(context_window=16385, safe_limit=15000)
        
        # Default conservative limits
        else:
            logger.warning(f"Unknown model {model_name}, using conservative limits")
            return cls(context_window=8192, safe_limit=7000)


class TokenEstimator:
    """Estimates token count for different content types"""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Rough token estimation (1 token ≈ 4 characters for English)
        This is approximate but fast. For precise counting, we'd need tiktoken/Claude tokenizer
        """
        if not text:
            return 0
        
        # Handle non-string types that might be passed (like lists from selected_bots)
        if not isinstance(text, str):
            # Convert to string representation
            text = str(text)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Rough estimation: 1 token per 4 characters
        # Add some buffer for special tokens, formatting, etc.
        char_count = len(cleaned)
        token_estimate = max(1, int(char_count / 3.5))  # Slightly conservative
        
        return token_estimate
    
    @staticmethod
    def estimate_message_tokens(role: str, content: str) -> int:
        """Estimate tokens for a message including role overhead"""
        content_tokens = TokenEstimator.estimate_tokens(content)
        role_overhead = 5  # Approximate overhead for role, formatting, etc.
        return content_tokens + role_overhead


class ContextManager:
    """Manages context size to prevent overflow"""
    
    def __init__(self, model_name: str):
        self.model_limits = ModelLimits.get_limits(model_name)
        self.model_name = model_name
    
    def estimate_current_context(
        self,
        system_prompt: str,
        conversation_history: List[Any],
        current_message: str,
        tool_results: List[str] = None,
        citation_context: str = None
    ) -> int:
        """Estimate total context size"""
        
        total_tokens = 0
        
        # System prompt
        total_tokens += TokenEstimator.estimate_tokens(system_prompt)
        
        # Conversation history
        for msg in conversation_history:
            if hasattr(msg, 'content'):
                role = "user" if "Human" in str(type(msg)) else "assistant"
                total_tokens += TokenEstimator.estimate_message_tokens(role, msg.content)
        
        # Current message
        total_tokens += TokenEstimator.estimate_message_tokens("user", current_message)
        
        # Tool results (if any)
        if tool_results:
            for result in tool_results:
                total_tokens += TokenEstimator.estimate_tokens(str(result))
        
        # Citation context
        if citation_context:
            total_tokens += TokenEstimator.estimate_tokens(citation_context)
        
        return total_tokens
    
    def truncate_conversation_history(
        self,
        conversation_history: List[Any],
        reserved_tokens: int = 20000  # Reserve for system prompt, current message, tools
    ) -> List[Any]:
        """
        Truncate conversation history to fit within context limits
        Keeps the most recent messages and tries to maintain conversation pairs
        """
        
        if not conversation_history:
            return []
        
        available_tokens = self.model_limits.safe_limit - reserved_tokens
        
        # Start from most recent and work backwards
        truncated_history = []
        current_tokens = 0
        
        # Process messages in reverse order (most recent first)
        for msg in reversed(conversation_history):
            if hasattr(msg, 'content'):
                role = "user" if "Human" in str(type(msg)) else "assistant"
                msg_tokens = TokenEstimator.estimate_message_tokens(role, msg.content)
                
                if current_tokens + msg_tokens <= available_tokens:
                    truncated_history.insert(0, msg)  # Insert at beginning
                    current_tokens += msg_tokens
                else:
                    break
        
        removed_count = len(conversation_history) - len(truncated_history)
        if removed_count > 0:
            logger.info(
                f"Truncated conversation history: removed {removed_count} messages, "
                f"kept {len(truncated_history)} messages (~{current_tokens} tokens)"
            )
        
        return truncated_history
    
    def truncate_tool_result(self, tool_result: str, max_tokens: int = 8000) -> str:
        """
        Truncate tool result if it's too large
        Tries to keep important parts (beginning and end)
        """
        
        estimated_tokens = TokenEstimator.estimate_tokens(tool_result)
        
        if estimated_tokens <= max_tokens:
            return tool_result
        
        # Calculate how much text we can keep
        max_chars = max_tokens * 3.5  # Rough conversion back to characters
        
        if len(tool_result) <= max_chars:
            return tool_result
        
        # Keep beginning and end, with truncation indicator
        keep_length = int(max_chars * 0.8)  # 80% of available space
        start_length = int(keep_length * 0.7)  # 70% from start
        end_length = keep_length - start_length  # 30% from end
        
        if len(tool_result) <= start_length + end_length + 200:
            return tool_result
        
        truncated = (
            tool_result[:start_length] + 
            f"\n\n[... TRUNCATED: {len(tool_result) - start_length - end_length} characters removed for context size management ...]\n\n" +
            tool_result[-end_length:]
        )
        
        logger.info(
            f"Truncated tool result: {len(tool_result)} → {len(truncated)} chars "
            f"(~{estimated_tokens} → ~{TokenEstimator.estimate_tokens(truncated)} tokens)"
        )
        
        return truncated
    
    def check_context_safety(
        self,
        system_prompt: str,
        conversation_history: List[Any],
        current_message: str,
        tool_results: List[str] = None,
        citation_context: str = None
    ) -> Tuple[bool, int, int]:
        """
        Check if current context is within safe limits
        
        Returns:
            (is_safe, current_tokens, limit)
        """
        
        current_tokens = self.estimate_current_context(
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            current_message=current_message,
            tool_results=tool_results,
            citation_context=citation_context
        )
        
        is_safe = current_tokens <= self.model_limits.safe_limit
        
        return is_safe, current_tokens, self.model_limits.safe_limit
    
    def optimize_context(
        self,
        system_prompt: str,
        conversation_history: List[Any],
        current_message: str,
        tool_results: List[str] = None,
        citation_context: str = None
    ) -> Tuple[List[Any], List[str], str]:
        """
        Optimize context to fit within limits
        
        Returns:
            (optimized_history, optimized_tool_results, optimized_citation_context)
        """
        
        # First pass: check if we need optimization
        is_safe, current_tokens, limit = self.check_context_safety(
            system_prompt, conversation_history, current_message, 
            tool_results, citation_context
        )
        
        if is_safe:
            logger.info(f"Context is safe: {current_tokens}/{limit} tokens")
            return conversation_history, tool_results or [], citation_context or ""
        
        logger.warning(f"Context overflow: {current_tokens}/{limit} tokens - optimizing...")
        
        # Optimize tool results first (they can be very large)
        optimized_tool_results = []
        if tool_results:
            for result in tool_results:
                optimized_tool_results.append(self.truncate_tool_result(result))
        
        # Optimize citation context (keep most important parts)
        optimized_citation_context = citation_context
        if citation_context and len(citation_context) > 2000:
            lines = citation_context.split('\n')
            if len(lines) > 20:  # Keep first few and last few lines
                optimized_citation_context = '\n'.join(lines[:10] + ['[... truncated ...]'] + lines[-5:])
        
        # Calculate tokens used by non-history content
        non_history_tokens = (
            TokenEstimator.estimate_tokens(system_prompt) +
            TokenEstimator.estimate_message_tokens("user", current_message) +
            sum(TokenEstimator.estimate_tokens(result) for result in optimized_tool_results) +
            TokenEstimator.estimate_tokens(optimized_citation_context or "")
        )
        
        # Reserve space for response
        reserved_tokens = non_history_tokens + 5000  # 5K for response
        
        # Truncate conversation history
        optimized_history = self.truncate_conversation_history(
            conversation_history, 
            reserved_tokens=reserved_tokens
        )
        
        # Final check
        is_safe_final, final_tokens, _ = self.check_context_safety(
            system_prompt, optimized_history, current_message,
            optimized_tool_results, optimized_citation_context
        )
        
        logger.info(
            f"Context optimization complete: {current_tokens} → {final_tokens} tokens "
            f"(safe: {is_safe_final})"
        )
        
        return optimized_history, optimized_tool_results, optimized_citation_context or "" 