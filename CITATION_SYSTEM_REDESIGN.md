# Citation System Redesign

## Overview

We've completely redesigned Scintilla's citation system to be more reliable, flexible, and maintainable. The new system separates concerns properly and ensures citations are handled consistently.

## Key Improvements

### 1. **Separation of Concerns**

**Before:**
- Citation extraction happened during tool execution (mid-flow)
- Citation context was added between tool iterations
- Post-processing tried to fix citations after the fact
- Tight coupling between tool results and citation format

**After:**
- Tool execution only collects metadata (URLs, titles, identifiers)
- Citation guidance is built once, after all tools complete
- Final LLM call handles all citation formatting with full context
- Clean separation between data extraction and presentation

### 2. **Flexible Metadata Extraction**

The new `ToolResultProcessor` extracts metadata without assumptions:

```python
@dataclass
class ToolResultMetadata:
    urls: List[str]              # All URLs found
    titles: List[str]            # Potential titles
    identifiers: Dict[str, str]  # Tickets, PRs, file IDs, etc.
    source_type: str             # jira, github, gdrive, etc.
    snippet: str                 # Preview of content
```

This works for ANY tool type without tool-specific code in the main flow.

### 3. **Reliable Citation Flow**

```
1. Tool Execution Phase:
   - Execute tools normally
   - Extract metadata flexibly
   - Store all metadata for later

2. Final Response Phase:
   - Build citation guidance from ALL metadata
   - Single LLM call with complete context
   - LLM decides how to cite based on guidance
   - Post-process to add clickable links

3. Source Filtering:
   - Only include sources actually cited [1], [2], etc.
   - Automatic cleanup of unused sources
```

### 4. **Better Citation Guidance**

The LLM receives clear, structured citation information:

```
[1] MKT-1183: Update marketing dashboard
   URL: https://mycompany.atlassian.net/browse/MKT-1183
   Ticket: MKT-1183
   Type: jira

[2] Pull Request #123: Fix authentication bug
   URL: https://github.com/myorg/myrepo/pull/123
   PR: #123
   Type: github
```

With explicit instructions:
- Use [1], [2], [3] format for citations
- Make identifiers clickable with markdown
- Only cite when referencing specific information

### 5. **Automatic Link Creation**

Post-processing automatically converts identifiers to clickable links:
- `MKT-1183` → `[MKT-1183](https://mycompany.atlassian.net/browse/MKT-1183)`
- Works for any identifier with a URL mapping
- No manual URL construction needed

## Benefits

### Reliability
✅ **Consistent citations** - Single LLM call with full context
✅ **No lost citations** - Metadata preserved throughout flow
✅ **Proper numbering** - LLM sees all sources at once

### Flexibility
✅ **Any tool type** - No tool-specific citation code
✅ **Any URL pattern** - Flexible extraction patterns
✅ **Any identifier** - Tickets, PRs, docs, etc.

### Maintainability
✅ **Clean separation** - Data vs presentation
✅ **Single responsibility** - Each component has one job
✅ **Easy to extend** - Add new patterns to processor

### Performance
✅ **Efficient** - Metadata extraction is fast
✅ **Scalable** - Works with many tools/sources
✅ **Context-aware** - Integrates with context management

## Implementation Details

### ToolResultProcessor
- Extracts URLs using multiple patterns
- Identifies tickets, PRs, file IDs automatically
- Determines source type from tool name and content
- Enhances metadata with tool parameters

### Citation Guidance Builder
- Creates numbered source list
- Includes all relevant metadata
- Formats for LLM comprehension
- Provides clear instructions

### Link Creation
- Maps identifiers to URLs
- Uses regex for reliable replacement
- Handles multiple identifier types
- Preserves original text structure

### Source Filtering
- Parses final content for [N] citations
- Only includes referenced sources
- Maintains citation order
- Cleans up unused metadata

## Migration Notes

### Removed Components
- `CitationManager` class (no longer needed)
- `SimpleSourceExtractor` (replaced by `ToolResultProcessor`)
- Mid-flow citation context injection
- Post-processing LLM call for citations

### New Components
- `ToolResultProcessor` - Flexible metadata extraction
- `ToolResultMetadata` - Structured metadata storage
- Citation guidance builder in main flow
- Simplified link creation logic

### API Changes
- `_execute_tool_calls()` now returns metadata
- Citation handling moved to end of query
- Sources built from metadata, not citation manager

## Testing

Run the test suite to verify:
```bash
python scripts/test_citation_system.py
```

This tests:
- Metadata extraction for various tools
- Citation guidance generation
- Clickable link creation
- End-to-end citation flow

## Future Enhancements

1. **Richer Metadata**: Extract more context (authors, dates, etc.)
2. **Smart Grouping**: Group related sources automatically
3. **Citation Styles**: Support different citation formats
4. **Preview Generation**: Better snippets for sources
5. **Duplicate Detection**: Merge duplicate sources intelligently 