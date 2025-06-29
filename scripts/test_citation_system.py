#!/usr/bin/env python3
"""
Test the new flexible citation system

Tests the tool result processor and citation generation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_result_processor import ToolResultProcessor, ToolResultMetadata

def test_jira_result():
    """Test processing Jira search results"""
    print("=== Testing Jira Result Processing ===")
    
    # Simulate Jira search result
    jira_result = """
    {
        "issues": [
            {
                "key": "MKT-1183",
                "fields": {
                    "summary": "Update marketing dashboard",
                    "status": {"name": "In Progress"},
                    "created": "2024-01-15T10:30:00Z"
                }
            },
            {
                "key": "MKT-1184", 
                "fields": {
                    "summary": "Q1 campaign planning",
                    "status": {"name": "To Do"},
                    "created": "2024-01-16T14:20:00Z"
                }
            }
        ],
        "self": "https://mycompany.atlassian.net/rest/api/2/search"
    }
    """
    
    metadata = ToolResultProcessor.process_tool_result(
        tool_name="jira_search_issues",
        tool_result=jira_result,
        tool_params={"jql": "project=MKT"}
    )
    
    print(f"URLs found: {metadata.urls}")
    print(f"Titles found: {metadata.titles}")
    print(f"Identifiers: {metadata.identifiers}")
    print(f"Source type: {metadata.source_type}")

def test_github_result():
    """Test processing GitHub results"""
    print("\n=== Testing GitHub Result Processing ===")
    
    github_result = """
    ## Pull Request #123: Fix authentication bug
    
    This PR fixes the authentication issue reported in issue #456.
    
    URL: https://github.com/myorg/myrepo/pull/123
    
    Changes:
    - Updated auth.py
    - Added tests
    """
    
    metadata = ToolResultProcessor.process_tool_result(
        tool_name="github_get_pull_request",
        tool_result=github_result,
        tool_params={"owner": "myorg", "repo": "myrepo", "pr_number": 123}
    )
    
    print(f"URLs found: {metadata.urls}")
    print(f"Titles found: {metadata.titles}")
    print(f"Identifiers: {metadata.identifiers}")
    print(f"Source type: {metadata.source_type}")

def test_google_drive_result():
    """Test processing Google Drive results"""
    print("\n=== Testing Google Drive Result Processing ===")
    
    drive_result = """
    Document: Q4 Financial Report
    
    This document contains the Q4 2023 financial results...
    
    Link: https://docs.google.com/document/d/1234567890abcdef/edit
    """
    
    metadata = ToolResultProcessor.process_tool_result(
        tool_name="gdrive_read_file",
        tool_result=drive_result,
        tool_params={"file_id": "1234567890abcdef"}
    )
    
    print(f"URLs found: {metadata.urls}")
    print(f"Titles found: {metadata.titles}")
    print(f"Identifiers: {metadata.identifiers}")
    print(f"Source type: {metadata.source_type}")

def test_citation_guidance():
    """Test building citation guidance"""
    print("\n=== Testing Citation Guidance Building ===")
    
    # Simulate tool metadata collection
    tool_metadata = [
        {
            "tool_name": "jira_search",
            "tool_args": {"jql": "project=MKT"},
            "metadata": {
                "urls": ["https://mycompany.atlassian.net/browse/MKT-1183"],
                "titles": ["MKT-1183: Update marketing dashboard"],
                "identifiers": {"primary_ticket": "MKT-1183", "tickets": "MKT-1183,MKT-1184"},
                "source_type": "jira"
            }
        },
        {
            "tool_name": "github_search",
            "tool_args": {"query": "auth bug"},
            "metadata": {
                "urls": ["https://github.com/myorg/myrepo/pull/123"],
                "titles": ["Pull Request #123: Fix authentication bug"],
                "identifiers": {"pr_number": "123"},
                "source_type": "github"
            }
        }
    ]
    
    # Build citation guidance (simulating what the agent does)
    citation_lines = []
    source_num = 1
    
    for meta in tool_metadata:
        tool_name = meta['tool_name']
        metadata = meta['metadata']
        
        citation_parts = []
        
        if metadata.get('titles'):
            citation_parts.append(f"[{source_num}] {metadata['titles'][0]}")
        else:
            citation_parts.append(f"[{source_num}] {tool_name} results")
        
        if metadata.get('urls'):
            citation_parts.append(f"   URL: {metadata['urls'][0]}")
        
        if metadata.get('identifiers'):
            ids = metadata['identifiers']
            if ids.get('primary_ticket'):
                citation_parts.append(f"   Ticket: {ids['primary_ticket']}")
            if ids.get('pr_number'):
                citation_parts.append(f"   PR: #{ids['pr_number']}")
        
        if metadata.get('source_type'):
            citation_parts.append(f"   Type: {metadata['source_type']}")
        
        citation_lines.extend(citation_parts)
        citation_lines.append("")
        source_num += 1
    
    citation_guidance = "\n".join(citation_lines)
    print("Citation Guidance for LLM:")
    print(citation_guidance)

def test_link_creation():
    """Test creating clickable links"""
    print("\n=== Testing Clickable Link Creation ===")
    
    import re
    
    content = """
    I found the following tickets:
    - MKT-1183 is about updating the dashboard
    - MKT-1184 is for Q1 planning
    
    Also, PR #123 fixes the authentication bug.
    """
    
    # Simulate identifier to URL mapping
    id_to_url = {
        "MKT-1183": "https://mycompany.atlassian.net/browse/MKT-1183",
        "MKT-1184": "https://mycompany.atlassian.net/browse/MKT-1184"
    }
    
    def replace_identifier(match):
        identifier = match.group(1)
        if identifier in id_to_url:
            url = id_to_url[identifier]
            return f'[{identifier}]({url})'
        return identifier
    
    ticket_pattern = r'\b([A-Z][A-Z0-9]*-\d+)\b'
    processed_content = re.sub(ticket_pattern, replace_identifier, content)
    
    print("Original content:")
    print(content)
    print("\nProcessed content with clickable links:")
    print(processed_content)

def main():
    """Run all tests"""
    print("🧪 Testing Scintilla Flexible Citation System\n")
    
    test_jira_result()
    test_github_result()
    test_google_drive_result()
    test_citation_guidance()
    test_link_creation()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main() 