import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ExternalLink } from 'lucide-react'

/**
 * Component for rendering citation numbers [1], [2], etc.
 */
export const CitationLink = ({ number, onClick, className = "" }) => {
  return (
    <span
      className={`citation-link inline-flex items-center text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 px-1 py-0.5 rounded ${className}`}
      title={`Source ${number}`}
    >
      [{number}]
    </span>
  )
}

/**
 * Component for rendering a list of sources/references
 */
export const ReferenceList = ({ sources, className = "" }) => {
  if (!sources || sources.length === 0) {
    return null
  }

  const formatUrl = (url, title) => {
    if (!url || url === "https://drive.google.com") {
      return null
    }
    
    // For Google Drive URLs, show a cleaner display text
    if (url.includes('docs.google.com') || url.includes('drive.google.com')) {
      return {
        href: url,
        display: `Google Drive: ${title}`,
        icon: '📄'
      }
    }
    
    // For other URLs, show the domain
    try {
      const domain = new URL(url).hostname
      return {
        href: url,
        display: domain,
        icon: '🌐'
      }
    } catch {
      return {
        href: url,
        display: url,
        icon: '🔗'
      }
    }
  }

  return (
    <div className={`reference-list mt-4 pt-4 border-t border-gray-200 dark:border-gray-600 ${className}`}>
      <h4 className="font-semibold text-sm text-gray-700 dark:text-gray-300 mb-3 flex items-center">
        <span>Sources</span>
        <span className="ml-2 text-xs text-gray-500 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">
          {sources.length}
        </span>
      </h4>
      <div className="space-y-2">
        {sources.map((source, index) => {
          const urlInfo = formatUrl(source.url, source.title)
          
          return (
            <div 
              key={index} 
              id={`ref-${index + 1}`} 
              className="text-xs text-gray-600 dark:text-gray-400 flex items-start space-x-2 p-2 rounded bg-gray-50 dark:bg-gray-800"
            >
              <span className="font-medium text-blue-600 dark:text-blue-400 min-w-[1.5rem]">
                [{index + 1}]
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2">
                  <span className="font-medium text-gray-700 dark:text-gray-300 truncate">
                    {source.title}
                  </span>
                  <SourceTypeIcon type={source.source_type} />
                </div>
                {urlInfo && (
                  <a 
                    href={urlInfo.href} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-blue-600 dark:text-blue-400 hover:underline flex items-center space-x-1 mt-1"
                  >
                    <span className="text-xs">{urlInfo.icon}</span>
                    <span className="truncate">{urlInfo.display}</span>
                    <ExternalLink className="h-3 w-3 flex-shrink-0" />
                  </a>
                )}
                {source.snippet && (
                  <p className="text-gray-500 dark:text-gray-500 mt-1 text-xs line-clamp-2">
                    {source.snippet}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/**
 * Icon component for different source types
 */
const SourceTypeIcon = ({ type }) => {
  const iconClass = "h-3 w-3 flex-shrink-0"
  
  switch (type) {
    case 'google_drive':
      return (
        <span className={`${iconClass} text-green-600`} title="Google Drive">
          📄
        </span>
      )
    case 'github':
      return (
        <span className={`${iconClass} text-gray-800 dark:text-gray-200`} title="GitHub">
          🐙
        </span>
      )
    case 'jira':
    case 'jira_issue':
      return (
        <span className={`${iconClass} text-blue-600`} title="Jira Issue">
          🎫
        </span>
      )
    case 'confluence':
      return (
        <span className={`${iconClass} text-blue-500`} title="Confluence">
          📚
        </span>
      )
    case 'search':
      return (
        <span className={`${iconClass} text-blue-600`} title="Search Result">
          🔍
        </span>
      )
    case 'web':
    case 'web_api':
      return (
        <span className={`${iconClass} text-purple-600`} title="Web">
          🌐
        </span>
      )
    case 'mcp_tool':
      return (
        <span className={`${iconClass} text-orange-600`} title="MCP Tool">
          🔧
        </span>
      )
    default:
      return (
        <span className={`${iconClass} text-gray-500`} title="Document">
          📋
        </span>
      )
  }
}

/**
 * Universal function to process any text content and replace citations with clickable links
 */
const processCitations = (content, sources, onCitationClick) => {
  if (typeof content !== 'string') {
    return content
  }

  const citationRegex = /\[(\d+)\]/g
  const parts = []
  let lastIndex = 0
  let match

  while ((match = citationRegex.exec(content)) !== null) {
    // Add text before citation
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index))
    }

    // Add citation link
    const citationNumber = parseInt(match[1])
    parts.push(
      <CitationLink
        key={`citation-${citationNumber}-${match.index}-${Math.random()}`}
        number={citationNumber}
        onClick={onCitationClick}
        className="mx-0.5"
      />
    )

    lastIndex = match.index + match[0].length
  }

  // Add remaining text
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex))
  }

  return parts.length > 1 ? parts : content
}

/**
 * Process children to handle citations in any context
 */
const processChildrenWithCitations = (children, sources, onCitationClick) => {
  return React.Children.map(children, (child, index) => {
    if (typeof child === 'string') {
      return processCitations(child, sources, onCitationClick)
    }
    return child
  })
}

/**
 * Custom components for rendering Markdown with citation support
 */
const createMarkdownComponents = (sources, content, onCitationClick) => ({
  // Custom renderer for paragraphs to handle citations
  p: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return (
      <p className="mb-3 text-gray-700 dark:text-gray-300 leading-relaxed">
        {processedChildren}
      </p>
    )
  },

  // Process citations in list items
  li: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return <li className="ml-2">{processedChildren}</li>
  },

  // Process citations in headers
  h1: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return (
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4 mt-6">{processedChildren}</h1>
    )
  },
  h2: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return (
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-3 mt-5">{processedChildren}</h2>
    )
  },
  h3: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return (
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 mt-4">{processedChildren}</h3>
    )
  },
  h4: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return (
      <h4 className="text-base font-semibold text-gray-900 dark:text-white mb-2 mt-3">{processedChildren}</h4>
    )
  },

  // Process citations in emphasis and strong text
  strong: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return (
      <strong className="font-semibold text-gray-900 dark:text-white">{processedChildren}</strong>
    )
  },
  em: ({ children }) => {
    const processedChildren = processChildrenWithCitations(children, sources, onCitationClick)
    return (
      <em className="italic text-gray-700 dark:text-gray-300">{processedChildren}</em>
    )
  },
  
  // Basic styling for common Markdown elements
  ul: ({ children }) => (
    <ul className="list-disc list-inside mb-3 text-gray-700 dark:text-gray-300 space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside mb-3 text-gray-700 dark:text-gray-300 space-y-1">{children}</ol>
  ),
  code: ({ children, inline }) => (
    inline ? (
      <code className="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 px-1 py-0.5 rounded text-sm font-mono">
        {children}
      </code>
    ) : (
      <pre className="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 p-3 rounded text-sm font-mono overflow-x-auto">
        <code>{children}</code>
      </pre>
    )
  )
})

/**
 * Main component for rendering message content with citations
 */
export const CitationRenderer = ({ content, sources = [], onCitationClick }) => {
  if (!content) {
    return null
  }

  const handleCitationClick = (citationNumber) => {
    // Scroll to reference
    const refElement = document.getElementById(`ref-${citationNumber}`)
    if (refElement) {
      refElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      // Brief highlight effect
      refElement.classList.add('bg-yellow-100', 'dark:bg-yellow-900')
      setTimeout(() => {
        refElement.classList.remove('bg-yellow-100', 'dark:bg-yellow-900')
      }, 2000)
    }
    
    // Call external handler if provided
    onCitationClick?.(citationNumber)
  }

  // Clean content by removing LLM-generated Sources sections
  const cleanedContent = content
    .replace(/\*\*Sources:\*\*[\s\S]*?(?=\n\n|\n$|$)/g, '')  // Remove **Sources:** sections
    .replace(/## Sources[\s\S]*?(?=\n\n|\n$|$)/g, '')        // Remove ## Sources sections
    .replace(/^Sources[\s\S]*?(?=\n\n|\n$|$)/gm, '')         // Remove Sources sections that start at beginning of line
    .replace(/<SOURCES>[\s\S]*?<\/SOURCES>/g, '')            // Remove <SOURCES> delimited sections
    .trim()

  // Fallback to simple text rendering if Markdown fails
  const renderFallback = () => {
    // Process citations in fallback content too
    const processedFallback = processCitations(cleanedContent, sources, handleCitationClick)
    return (
      <div className="content whitespace-pre-wrap text-gray-700 dark:text-gray-300">
        {processedFallback}
      </div>
    )
  }

  try {
    return (
      <div className="citation-content">
        <div className="content prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={createMarkdownComponents(sources, content, handleCitationClick)}
          >
            {cleanedContent}
          </ReactMarkdown>
        </div>
        {/* Always show the boxed Sources section if we have sources */}
        {sources && sources.length > 0 && (
          <ReferenceList sources={sources} />
        )}
      </div>
    )
  } catch (error) {
    console.error('Markdown rendering error:', error)
    // Fallback to simple text rendering
    return (
      <div className="citation-content">
        {renderFallback()}
        {/* Always show the boxed Sources section if we have sources */}
        {sources && sources.length > 0 && (
          <ReferenceList sources={sources} />
        )}
      </div>
    )
  }
}

export default CitationRenderer 