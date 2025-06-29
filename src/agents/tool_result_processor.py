"""
Tool Result Processor for Scintilla

Handles flexible extraction of citations, URLs, and metadata from tool results.
This replaces the rigid citation extraction with a more flexible system.
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class ToolResultMetadata:
    """Metadata extracted from a tool result"""
    urls: List[str] = field(default_factory=list)
    titles: List[str] = field(default_factory=list)
    identifiers: Dict[str, str] = field(default_factory=dict)  # e.g., {"ticket": "JIRA-123", "pr": "123"}
    source_type: str = ""
    snippet: str = ""
    raw_data: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'urls': self.urls,
            'titles': self.titles,
            'identifiers': self.identifiers,
            'source_type': self.source_type,
            'snippet': self.snippet
        }


class ToolResultProcessor:
    """
    Flexible tool result processor that extracts metadata without rigid assumptions.
    
    The goal is to extract useful information that can be used for citations,
    but let the LLM decide how to use it in the final response.
    """
    
    @staticmethod
    def process_tool_result(
        tool_name: str, 
        tool_result: Any, 
        tool_params: Dict[str, Any] = None
    ) -> ToolResultMetadata:
        """
        Process a tool result and extract useful metadata.
        
        This is designed to be flexible and extract whatever information
        is available without making assumptions about how it will be used.
        """
        metadata = ToolResultMetadata()
        
        # Convert result to string for analysis
        result_str = str(tool_result) if tool_result else ""
        
        # Skip failed tool calls
        if len(result_str.strip()) < 50 or "Error calling tool" in result_str:
            logger.debug(f"Skipping failed tool result: {tool_name}")
            return metadata
        
        # Store raw data for later processing
        metadata.raw_data = tool_result
        
        # Extract URLs
        metadata.urls = ToolResultProcessor._extract_urls(result_str)
        
        # Extract identifiers (ticket IDs, PR numbers, etc.)
        metadata.identifiers = ToolResultProcessor._extract_identifiers(result_str, tool_name)
        
        # Extract titles
        metadata.titles = ToolResultProcessor._extract_titles(result_str, tool_name)
        
        # Determine source type
        metadata.source_type = ToolResultProcessor._determine_source_type(tool_name, result_str, metadata.urls)
        
        # Create snippet
        metadata.snippet = result_str[:500] + "..." if len(result_str) > 500 else result_str
        
        # Tool-specific enhancements
        if tool_params:
            ToolResultProcessor._enhance_with_tool_params(metadata, tool_name, tool_params)
        
        logger.debug(
            f"Processed tool result",
            tool=tool_name,
            urls_found=len(metadata.urls),
            titles_found=len(metadata.titles),
            identifiers=list(metadata.identifiers.keys())
        )
        
        return metadata
    
    @staticmethod
    def _extract_urls(content: str) -> List[str]:
        """Extract all URLs from content"""
        urls = []
        
        # Comprehensive URL patterns
        url_patterns = [
            # Standard URLs
            r'https?://[^\s\)>\]"\']+',
            # Markdown links
            r'\[.*?\]\((https?://[^\)]+)\)',
            # HTML links
            r'href=["\']?(https?://[^"\'>\s]+)',
            # JSON fields
            r'"(?:url|html_url|web_url|browse_url|permalink|link|href)":\s*"(https?://[^"]+)"',
        ]
        
        seen_urls = set()
        for pattern in url_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0]
                # Clean up URL
                url = url.strip().rstrip('.,;:')
                # Skip images and duplicates
                if url and url not in seen_urls and not url.endswith(('.png', '.jpg', '.gif', '.svg')):
                    seen_urls.add(url)
                    urls.append(url)
        
        return urls
    
    @staticmethod
    def _extract_identifiers(content: str, tool_name: str) -> Dict[str, str]:
        """Extract various identifiers from content"""
        identifiers = {}
        
        # Jira/Issue tickets
        ticket_pattern = r'\b([A-Z][A-Z0-9]*-\d+)\b'
        tickets = re.findall(ticket_pattern, content)
        if tickets:
            # Store all tickets, but also the first one as primary
            identifiers['tickets'] = ','.join(set(tickets[:10]))  # Limit to 10
            identifiers['primary_ticket'] = tickets[0]
        
        # GitHub PR/Issue numbers
        if 'github' in tool_name.lower() or 'github.com' in content:
            pr_pattern = r'(?:PR|pull request|#)[\s#]*(\d+)'
            issue_pattern = r'(?:issue|#)[\s#]*(\d+)'
            
            pr_matches = re.findall(pr_pattern, content, re.IGNORECASE)
            if pr_matches:
                identifiers['pr_number'] = pr_matches[0]
            
            issue_matches = re.findall(issue_pattern, content, re.IGNORECASE)
            if issue_matches:
                identifiers['issue_number'] = issue_matches[0]
        
        # File paths
        file_pattern = r'(?:^|[\s"])([/\\]?(?:[a-zA-Z0-9_\-]+[/\\])*[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)'
        file_matches = re.findall(file_pattern, content)
        if file_matches:
            identifiers['file_path'] = file_matches[0]
        
        # Document IDs (Google Drive, etc.)
        doc_id_pattern = r'(?:document/d/|file/d/|id=)([a-zA-Z0-9_\-]{20,})'
        doc_matches = re.findall(doc_id_pattern, content)
        if doc_matches:
            identifiers['document_id'] = doc_matches[0]
        
        return identifiers
    
    @staticmethod
    def _extract_titles(content: str, tool_name: str) -> List[str]:
        """Extract potential titles from content"""
        titles = []
        
        # Common title patterns
        title_patterns = [
            # Jira-style: "TICKET-123: Title"
            r'([A-Z]+-\d+):\s*([^\n\r]{5,100})',
            # Markdown headers
            r'^#{1,3}\s+([^\n\r]+)$',
            # JSON title fields
            r'"(?:title|name|summary|subject)":\s*"([^"]+)"',
            # HTML title
            r'<title>([^<]+)</title>',
            # Document name patterns
            r'(?:Document|File|Page):\s*([^\n\r]+)',
        ]
        
        seen_titles = set()
        for pattern in title_patterns:
            matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # For Jira-style, combine ticket and title
                    if len(match) == 2 and match[0] and match[1]:
                        title = f"{match[0]}: {match[1]}"
                    else:
                        title = match[-1]  # Take last group
                else:
                    title = match
                
                title = title.strip()
                if title and len(title) > 5 and title not in seen_titles:
                    seen_titles.add(title)
                    titles.append(title)
                    if len(titles) >= 5:  # Limit to 5 titles
                        break
        
        return titles
    
    @staticmethod
    def _determine_source_type(tool_name: str, content: str, urls: List[str]) -> str:
        """Determine the source type from tool name and content"""
        tool_lower = tool_name.lower()
        
        # Check tool name first
        source_type_map = {
            'jira': 'jira',
            'atlassian': 'jira',
            'github': 'github',
            'gdrive': 'google_drive',
            'drive': 'google_drive',
            'slack': 'slack',
            'confluence': 'confluence',
            'notion': 'notion',
            'sharepoint': 'sharepoint',
            'file': 'file_system',
            'web': 'web',
            'search': 'search'
        }
        
        for key, source_type in source_type_map.items():
            if key in tool_lower:
                return source_type
        
        # Check URLs
        for url in urls:
            if 'github.com' in url:
                return 'github'
            elif 'atlassian.net' in url or 'jira' in url:
                return 'jira'
            elif 'confluence' in url:
                return 'confluence'
            elif 'slack.com' in url:
                return 'slack'
            elif 'notion.so' in url:
                return 'notion'
            elif 'docs.google.com' in url or 'drive.google.com' in url:
                return 'google_drive'
            elif 'sharepoint.com' in url:
                return 'sharepoint'
        
        # Default
        return 'tool_result'
    
    @staticmethod
    def _enhance_with_tool_params(
        metadata: ToolResultMetadata, 
        tool_name: str, 
        tool_params: Dict[str, Any]
    ) -> None:
        """Enhance metadata with tool parameters"""
        
        # Add any URLs from parameters
        param_urls = []
        for key in ['url', 'link', 'href', 'web_url', 'html_url', 'browse_url']:
            if key in tool_params and isinstance(tool_params[key], str):
                param_urls.append(tool_params[key])
        
        # Add unique URLs
        for url in param_urls:
            if url and url not in metadata.urls:
                metadata.urls.append(url)
        
        # Add identifiers from parameters
        if 'issue_key' in tool_params:
            metadata.identifiers['issue_key'] = tool_params['issue_key']
        if 'ticket_id' in tool_params:
            metadata.identifiers['ticket_id'] = tool_params['ticket_id']
        if 'file_id' in tool_params:
            metadata.identifiers['file_id'] = tool_params['file_id']
        if 'pr_number' in tool_params:
            metadata.identifiers['pr_number'] = str(tool_params['pr_number'])
        
        # Construct URLs if we have enough information
        if metadata.source_type == 'jira' and 'base_url' in tool_params:
            base_url = tool_params['base_url']
            if metadata.identifiers.get('primary_ticket'):
                constructed_url = f"{base_url}/browse/{metadata.identifiers['primary_ticket']}"
                if constructed_url not in metadata.urls:
                    metadata.urls.insert(0, constructed_url)  # Add as primary URL
        
        elif metadata.source_type == 'github' and all(k in tool_params for k in ['owner', 'repo']):
            owner = tool_params['owner']
            repo = tool_params['repo']
            base_url = f"https://github.com/{owner}/{repo}"
            
            if metadata.identifiers.get('issue_number'):
                constructed_url = f"{base_url}/issues/{metadata.identifiers['issue_number']}"
                if constructed_url not in metadata.urls:
                    metadata.urls.insert(0, constructed_url)
            elif metadata.identifiers.get('pr_number'):
                constructed_url = f"{base_url}/pull/{metadata.identifiers['pr_number']}"
                if constructed_url not in metadata.urls:
                    metadata.urls.insert(0, constructed_url) 