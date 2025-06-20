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
    def extract_sources(tool_name: str, result_data: Any, tool_params: Dict[str, Any] = None) -> List[Source]:
        """
        Extract sources from tool results with flexible URL and document extraction for any tool type
        
        Args:
            tool_name: Name of the tool
            result_data: Tool result data in any format
            tool_params: Tool parameters (e.g., file_id, repo, issue_id for various tools)
            
        Returns:
            List of source entries with proper URLs and metadata
        """
        sources = []
        
        # Convert result to string for analysis
        content = str(result_data)
        
        # Create a source entry for any tool result with meaningful content
        if content and len(content.strip()) > 20:
            # Step 1: Try to extract URLs directly from content (most reliable)
            url = SimpleSourceExtractor._extract_url_from_content(content, tool_name, tool_params)
            
            # Step 2: Determine source type and initial title
            source_type, title = SimpleSourceExtractor._determine_source_type_and_title(
                tool_name, content, tool_params, url
            )
            
            # Step 3: If no URL found, try tool-specific URL construction
            if not url:
                url = SimpleSourceExtractor._construct_url_from_tool_params(
                    tool_name, tool_params, content, source_type
                )
            
            # Step 4: Extract better title from content if available
            if title.startswith("Results from") or not title or len(title) < 5:
                extracted_title = SimpleSourceExtractor._extract_title_from_content(content, source_type)
                if extracted_title:
                    title = extracted_title
            
            sources.append(Source(
                title=title,
                url=url,
                source_type=source_type,
                snippet=content[:300] + "..." if len(content) > 300 else content,
                metadata={
                    'tool': tool_name,
                    'raw_content': content,
                    'content_length': len(content),
                    'tool_params': tool_params or {}
                }
            ))
        
        return sources
    
    @staticmethod
    def _extract_url_from_content(content: str, tool_name: str, tool_params: Dict[str, Any] = None) -> str:
        """Extract URLs directly from tool result content using common patterns"""
        # Common URL patterns to look for in tool results
        url_patterns = [
            # Complete URLs
            r'https?://[^\s\)>\]]+',
            # Markdown links [text](url)
            r'\[.*?\]\((https?://[^\)]+)\)',
            # HTML links
            r'href=["\']?(https?://[^"\'>\s]+)',
            # JSON API responses with url fields
            r'"url":\s*"(https?://[^"]+)"',
            r'"html_url":\s*"(https?://[^"]+)"',
            r'"web_url":\s*"(https?://[^"]+)"',
            r'"browse_url":\s*"(https?://[^"]+)"',
            r'"permalink":\s*"(https?://[^"]+)"',
            r'"link":\s*"(https?://[^"]+)"',
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Return the first meaningful URL found
                for match in matches:
                    url = match if isinstance(match, str) else match[0] if match else ""
                    if url and not url.endswith(('.png', '.jpg', '.gif', '.svg')):
                        return url.strip()
        
        return ""
    
    @staticmethod
    def _determine_source_type_and_title(tool_name: str, content: str, tool_params: Dict[str, Any] = None, url: str = "") -> tuple:
        """Determine source type and initial title based on tool name, content, and URL"""
        tool_lower = tool_name.lower()
        
        # Google Drive
        if "gdrive" in tool_lower or "drive" in tool_lower:
            if "search" in tool_lower:
                return "google_drive", "Google Drive Search Results"
            else:
                return "google_drive", "Google Drive Document"
        
        # GitHub
        elif "github" in tool_lower or "gh" in tool_lower:
            if "issue" in tool_lower or "issues" in tool_lower:
                return "github", "GitHub Issue"
            elif "pr" in tool_lower or "pull" in tool_lower:
                return "github", "GitHub Pull Request"
            elif "repo" in tool_lower:
                return "github", "GitHub Repository"
            else:
                return "github", "GitHub"
        
        # Jira/Atlassian
        elif "jira" in tool_lower or "atlassian" in tool_lower:
            if "issue" in tool_lower or "ticket" in tool_lower:
                return "jira", "Jira Issue"
            elif "project" in tool_lower:
                return "jira", "Jira Project"
            else:
                return "jira", "Jira"
        
        # Confluence
        elif "confluence" in tool_lower or "wiki" in tool_lower:
            return "confluence", "Confluence Page"
        
        # Slack
        elif "slack" in tool_lower:
            if "channel" in tool_lower:
                return "slack", "Slack Channel"
            elif "message" in tool_lower:
                return "slack", "Slack Message"
            else:
                return "slack", "Slack"
        
        # Notion
        elif "notion" in tool_lower:
            return "notion", "Notion Page"
        
        # SharePoint/Office365
        elif "sharepoint" in tool_lower or "office365" in tool_lower or "o365" in tool_lower:
            return "sharepoint", "SharePoint Document"
        
        # File systems
        elif "file" in tool_lower or "fs" in tool_lower:
            return "file_system", "File"
        
        # Web/HTTP APIs
        elif "http" in tool_lower or "web" in tool_lower or "api" in tool_lower:
            return "web_api", "Web API"
        
        # Search tools
        elif "search" in tool_lower:
            return "search", "Search Results"
        
        # Infer from URL if available
        elif url:
            if "github.com" in url:
                return "github", "GitHub"
            elif "jira" in url or "atlassian" in url:
                return "jira", "Jira"
            elif "confluence" in url:
                return "confluence", "Confluence"
            elif "slack.com" in url:
                return "slack", "Slack"
            elif "notion.so" in url:
                return "notion", "Notion"
            elif "sharepoint.com" in url or "office.com" in url:
                return "sharepoint", "SharePoint"
            elif "docs.google.com" in url or "drive.google.com" in url:
                return "google_drive", "Google Drive"
            else:
                return "web", "Web Resource"
        
        # Default
        else:
            return "tool_result", f"Results from {tool_name}"
    
    @staticmethod
    def _construct_url_from_tool_params(tool_name: str, tool_params: Dict[str, Any] = None, content: str = "", source_type: str = "") -> str:
        """Construct URLs from tool parameters when not found in content"""
        if not tool_params:
            return ""
        
        tool_lower = tool_name.lower()
        
        # Google Drive URL construction
        if source_type == "google_drive":
            file_id = tool_params.get("file_id") or tool_params.get("id")
            if file_id:
                # Infer document type from content or tool name
                if "spreadsheet" in content.lower() or "sheet" in tool_lower:
                    return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
                elif "document" in content.lower() or "doc" in tool_lower:
                    return f"https://docs.google.com/document/d/{file_id}/edit"
                elif "presentation" in content.lower() or "slide" in tool_lower:
                    return f"https://docs.google.com/presentation/d/{file_id}/edit"
                elif "folder" in content.lower():
                    return f"https://drive.google.com/drive/folders/{file_id}"
                else:
                    return f"https://drive.google.com/file/d/{file_id}/view"
        
        # GitHub URL construction
        elif source_type == "github":
            owner = tool_params.get("owner") or tool_params.get("org")
            repo = tool_params.get("repo") or tool_params.get("repository")
            issue_id = tool_params.get("issue_id") or tool_params.get("number")
            pr_id = tool_params.get("pr_id") or tool_params.get("pull_number")
            
            if owner and repo:
                base_url = f"https://github.com/{owner}/{repo}"
                if issue_id:
                    return f"{base_url}/issues/{issue_id}"
                elif pr_id:
                    return f"{base_url}/pull/{pr_id}"
                else:
                    return base_url
        
        # Jira URL construction
        elif source_type == "jira":
            base_url = tool_params.get("base_url") or tool_params.get("jira_url")
            issue_key = tool_params.get("issue_key") or tool_params.get("key")
            
            if base_url and issue_key:
                return f"{base_url}/browse/{issue_key}"
            elif base_url:
                return base_url
        
        # Confluence URL construction
        elif source_type == "confluence":
            base_url = tool_params.get("base_url") or tool_params.get("confluence_url")
            page_id = tool_params.get("page_id") or tool_params.get("id")
            
            if base_url and page_id:
                return f"{base_url}/pages/viewpage.action?pageId={page_id}"
            elif base_url:
                return base_url
        
        # Slack URL construction  
        elif source_type == "slack":
            workspace = tool_params.get("workspace") or tool_params.get("team")
            channel = tool_params.get("channel")
            ts = tool_params.get("ts") or tool_params.get("timestamp")
            
            if workspace and channel:
                base_url = f"https://{workspace}.slack.com/channels/{channel}"
                if ts:
                    return f"{base_url}/p{ts.replace('.', '')}"
                else:
                    return base_url
        
        # SharePoint URL construction
        elif source_type == "sharepoint":
            site_url = tool_params.get("site_url") or tool_params.get("sharepoint_url")
            item_id = tool_params.get("item_id") or tool_params.get("id")
            
            if site_url and item_id:
                return f"{site_url}/Forms/AllItems.aspx?id={item_id}"
            elif site_url:
                return site_url
        
        # Generic URL construction from common parameters
        url = (tool_params.get("url") or 
               tool_params.get("link") or 
               tool_params.get("href") or
               tool_params.get("web_url") or
               tool_params.get("html_url"))
        
        if url:
            return url
        
        return ""
    
    @staticmethod
    def _extract_title_from_content(content: str, source_type: str) -> str:
        """Extract meaningful titles from content based on source type and format"""
        # Try JSON parsing first for structured API data
        try:
            import json
            data = json.loads(content)
            
            # Common title fields in API responses
            title_fields = ['title', 'name', 'summary', 'subject', 'filename', 'displayName', 'key']
            for field in title_fields:
                if field in data and data[field]:
                    return str(data[field])[:100]  # Limit length
                    
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Source-specific title extraction
        if source_type == "google_drive":
            # Extract first file name from Google Drive search results
            file_matches = re.findall(r'(.*?) \(application/.*?\) - ID: ([a-zA-Z0-9_-]+)', content)
            if file_matches:
                title = file_matches[0][0].strip()
                if len(file_matches) > 1:
                    title += f" (+{len(file_matches)-1} more files found)"
                return title
        
        elif source_type == "github":
            # Extract repository name or issue title
            repo_match = re.search(r'github\.com/([^/\s]+/[^/\s]+)', content)
            if repo_match:
                return f"GitHub: {repo_match.group(1)}"
        
        elif source_type == "jira":
            # Extract issue key or title
            issue_match = re.search(r'([A-Z]+-\d+)', content)
            if issue_match:
                return f"Jira Issue: {issue_match.group(1)}"
        
        # Extract from first meaningful line for any content
        lines = content.split('\n')[:5]  # Check first few lines
        for line in lines:
            line = line.strip()
            # Skip empty lines, URLs, JSON, and very short/long lines
            if (line and 
                not line.startswith(('http', '{', '[')) and 
                10 <= len(line) <= 100 and
                not re.match(r'^[0-9.,\s]+$', line)):  # Skip pure numbers
                return line
        
        return ""


class SourceExtractor:
    """Extracts source information from different tool results"""
    
    @staticmethod
    def extract_from_tool_result(tool_name: str, tool_result: Dict[str, Any], tool_params: Dict[str, Any] = None) -> List[Source]:
        """
        Extract sources from tool results with enhanced URL extraction using tool parameters
        
        Args:
            tool_name: Name of the tool that generated the result
            tool_result: The tool result dictionary
            tool_params: Tool parameters (e.g., file_id for read operations)
            
        Returns:
            List of sources with proper URLs and metadata
        """
        sources = []
        
        try:
            if not tool_result.get('success', False):
                return sources
            
            result_data = tool_result.get('result', {})
            
            # Use enhanced extraction with tool parameters
            sources = SimpleSourceExtractor.extract_sources(tool_name, result_data, tool_params)
                
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