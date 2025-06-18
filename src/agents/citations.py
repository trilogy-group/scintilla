"""
Citation Management System for Scintilla

This module handles source extraction, citation numbering, and reference formatting
for maintaining proper academic-style citations in responses.
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class Source:
    """Represents a source document with citation information"""
    title: str
    url: str
    source_type: str  # 'google_drive', 'github', 'aise', 'web'
    snippet: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'url': self.url,
            'source_type': self.source_type,
            'snippet': self.snippet,
            'metadata': self.metadata
        }


class SimpleSourceExtractor:
    """Simple source extraction that provides hints to the LLM rather than trying to parse everything"""
    
    @staticmethod
    def extract_sources(tool_name: str, result_data: Any) -> List[Source]:
        """
        Simple source extraction that creates basic source entries for LLM guidance
        
        Args:
            tool_name: Name of the tool
            result_data: Tool result data in any format
            
        Returns:
            List of basic source hints for the LLM
        """
        sources = []
        
        # Convert result to string for analysis
        content = str(result_data)
        
        # Skip generic search results that don't point to specific files
        if (tool_name.endswith('_search') and 
            ('Found' in content or 'files:' in content) and
            len(content) < 2000):  # Short search result lists
            # Don't create a source for generic search results
            return sources
        
        # Create a simple source entry that gives the LLM context
        if content and len(content.strip()) > 50:  # Only if there's substantial content
            # Determine source type and title based on tool name
            source_type = "tool_result"
            title = f"Results from {tool_name}"
            
            if "gdrive" in tool_name.lower() or "drive" in tool_name.lower():
                source_type = "google_drive"
                if "read" in tool_name.lower():
                    title = "Google Drive Document"
                elif "search" in tool_name.lower():
                    title = "Google Drive Search Results"
            elif "github" in tool_name.lower():
                source_type = "github"
                if "read" in tool_name.lower() or "get" in tool_name.lower():
                    title = "GitHub Repository"
                elif "search" in tool_name.lower():
                    title = "GitHub Search Results"
            elif "search" in tool_name.lower():
                source_type = "search"
                title = "Search Results"
            
            # Only create source for meaningful content (not search results)
            if not tool_name.endswith('_search'):
                sources.append(Source(
                    title=title,
                    url="",  # Will be enhanced by backend with LLM-extracted URLs
                    source_type=source_type,
                    snippet=content[:300] + "..." if len(content) > 300 else content,
                    metadata={
                        'tool': tool_name,
                        'raw_content': content,
                        'content_length': len(content)
                    }
                ))
        
        return sources


class SourceExtractor:
    """Extracts source information from different tool results"""
    
    @staticmethod
    def extract_from_tool_result(tool_name: str, tool_result: Dict[str, Any]) -> List[Source]:
        """
        Extract sources from tool results using simple LLM-focused approach
        
        Args:
            tool_name: Name of the tool that generated the result
            tool_result: The tool result dictionary
            
        Returns:
            List of basic sources for LLM guidance
        """
        sources = []
        
        try:
            if not tool_result.get('success', False):
                return sources
            
            result_data = tool_result.get('result', {})
            
            # Use simple extraction that provides LLM hints
            sources = SimpleSourceExtractor.extract_sources(tool_name, result_data)
                
        except Exception as e:
            logger.warning(
                "Failed to extract sources from tool result",
                tool_name=tool_name,
                error=str(e)
            )
        
        return sources


class CitationManager:
    """Manages citations and source references throughout a conversation"""
    
    def __init__(self):
        self.sources: List[Source] = []
        self.url_to_citation: Dict[str, int] = {}
        self.next_citation_number = 1
    
    def add_sources(self, sources: List[Source]) -> List[int]:
        """
        Add sources and return their citation numbers
        
        Args:
            sources: List of Source objects to add
            
        Returns:
            List of citation numbers for the added sources
        """
        citation_numbers = []
        
        for source in sources:
            citation_num = self._get_or_create_citation(source)
            citation_numbers.append(citation_num)
        
        return citation_numbers
    
    def _get_or_create_citation(self, source: Source) -> int:
        """Get existing citation number or create new one"""
        # Use URL as primary key, fallback to title for sources without URLs
        key = source.url if source.url else f"title:{source.title}"
        
        if key in self.url_to_citation:
            return self.url_to_citation[key]
        
        # Create new citation
        citation_num = self.next_citation_number
        self.next_citation_number += 1
        
        self.sources.append(source)
        self.url_to_citation[key] = citation_num
        
        logger.debug(
            "Created new citation",
            citation_number=citation_num,
            title=source.title,
            source_type=source.source_type
        )
        
        return citation_num
    
    def get_citation_context_for_llm(self) -> str:
        """
        Generate citation context to include in LLM prompts
        
        Returns:
            Formatted string with available citations
        """
        if not self.sources:
            return ""
        
        context_lines = ["AVAILABLE SOURCES FOR CITATION:"]
        for i, source in enumerate(self.sources, 1):
            line = f"[{i}] {source.title}"
            if source.url:
                line += f" ({source.url})"
            if source.snippet:
                # Ensure snippet is a string
                snippet_str = str(source.snippet) if not isinstance(source.snippet, str) else source.snippet
                line += f" - {snippet_str[:100]}..."
            context_lines.append(line)
        
        context_lines.append("\nUSE [1], [2], [3] etc. to cite these sources in your response.")
        
        return "\n".join(context_lines)
    
    def generate_reference_list(self) -> str:
        """
        Generate formatted reference list for display
        
        Returns:
            Markdown-formatted reference list
        """
        if not self.sources:
            return ""
        
        ref_lines = ["## Sources\n"]
        for i, source in enumerate(self.sources, 1):
            if source.url:
                ref_lines.append(f"[{i}] [{source.title}]({source.url})")
            else:
                ref_lines.append(f"[{i}] {source.title}")
        
        return "\n".join(ref_lines)
    
    def get_sources_metadata(self) -> List[Dict[str, Any]]:
        """Get sources as serializable metadata"""
        return [source.to_dict() for source in self.sources]
    
    def clear(self):
        """Clear all citations and sources"""
        self.sources.clear()
        self.url_to_citation.clear()
        self.next_citation_number = 1 