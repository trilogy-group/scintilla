import { useState, useEffect, useCallback } from 'react'
import api from '../services/api'

export const useSourceSelector = () => {
  // Sources state
  const [availableSources, setAvailableSources] = useState([])
  const [selectedSources, setSelectedSources] = useState([]) // Array of selected source objects
  const [showSourceSelector, setShowSourceSelector] = useState(false)
  const [loading, setLoading] = useState(false)

  // Load sources from localStorage on initial load
  useEffect(() => {
    const savedSelection = localStorage.getItem('scintilla_selected_sources')
    if (savedSelection) {
      try {
        const parsed = JSON.parse(savedSelection)
        setSelectedSources(parsed)
      } catch (error) {
        console.error('Failed to parse saved source selection:', error)
        localStorage.removeItem('scintilla_selected_sources')
      }
    }
  }, [])

  // Save to localStorage whenever selection changes
  useEffect(() => {
    localStorage.setItem('scintilla_selected_sources', JSON.stringify(selectedSources))
  }, [selectedSources])

  // Load available sources for query selection
  const loadAvailableSources = useCallback(async () => {
    try {
      setLoading(true)
      console.log('Loading available sources for query selection...')
      const data = await api.getAvailableSourcesForQuery()
      console.log('Loaded available sources:', data.length)
      console.log('Source data details:', data.map(s => ({ 
        id: s.source_id, 
        name: s.name, 
        nameType: typeof s.name,
        nameLength: s.name ? s.name.length : 'null/undefined'
      })))
      setAvailableSources(data)
    } catch (error) {
      console.error('Failed to load available sources:', error)
      // Don't show error for authentication failures
      if (error.message?.includes('401') || error.message?.includes('Unauthorized')) {
        console.log('Authentication required for sources')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-load sources when hook is first used
  useEffect(() => {
    if (availableSources.length === 0) {
      loadAvailableSources()
    }
  }, [loadAvailableSources, availableSources.length])

  // Close selector when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      // Check if click is on the source selector
      const selector = document.querySelector('[data-source-selector="true"]')
      if (selector && !selector.contains(event.target)) {
        setShowSourceSelector(false)
      }
    }

    if (showSourceSelector) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [showSourceSelector])

  // Toggle source selection
  const toggleSourceSelection = useCallback((source) => {
    setSelectedSources(prev => {
      const isSelected = prev.find(s => s.source_id === source.source_id)
      if (isSelected) {
        // Remove source
        return prev.filter(s => s.source_id !== source.source_id)
      } else {
        // Add source
        return [...prev, source]
      }
    })
  }, [])

  // Check if source is selected
  const isSourceSelected = useCallback((sourceId) => {
    return selectedSources.some(source => source.source_id === sourceId)
  }, [selectedSources])

  // Clear all selected sources
  const clearSelectedSources = useCallback(() => {
    setSelectedSources([])
  }, [])

  // Get source IDs for query
  const getSelectedSourceIds = useCallback(() => {
    return selectedSources.map(source => source.source_id)
  }, [selectedSources])

  // Toggle selector visibility
  const toggleSelector = useCallback(() => {
    setShowSourceSelector(prev => !prev)
  }, [])

  // Close selector
  const closeSelector = useCallback(() => {
    setShowSourceSelector(false)
  }, [])

  // Manually reload selected sources from localStorage
  const reloadSelectedSources = useCallback(() => {
    console.log('Manually reloading selected sources from localStorage')
    const savedSelection = localStorage.getItem('scintilla_selected_sources')
    if (savedSelection) {
      try {
        const parsed = JSON.parse(savedSelection)
        console.log('Reloaded source selections:', parsed.length, parsed.map(s => s.name))
        setSelectedSources(parsed)
      } catch (error) {
        console.error('Failed to parse saved source selection during reload:', error)
        localStorage.removeItem('scintilla_selected_sources')
        setSelectedSources([])
      }
    } else {
      console.log('No saved source selections found in localStorage')
      setSelectedSources([])
    }
  }, [])

  return {
    // State
    availableSources,
    selectedSources,
    showSourceSelector,
    loading,

    // Functions
    loadAvailableSources,
    toggleSourceSelection,
    isSourceSelected,
    clearSelectedSources,
    getSelectedSourceIds,
    toggleSelector,
    closeSelector,
    reloadSelectedSources
  }
}

// Selected sources chips component
export const SelectedSourcesChips = ({ selectedSources, onToggleSource, className = "" }) => {
  if (selectedSources.length === 0) return null

  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {selectedSources.map((source) => (
        <div
          key={source.source_id}
          className="inline-flex items-center space-x-2 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-3 py-1.5 rounded-full text-sm border border-blue-200 dark:border-blue-800"
        >
          <div className="w-4 h-4 bg-gradient-to-r from-blue-500 to-blue-600 rounded-sm flex items-center justify-center flex-shrink-0">
            <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <span className="font-medium">{source.name || '[Unnamed Source]'}</span>
          
          {/* Source Type Indicator in chip */}
          {source.is_public ? (
            <svg className="h-3 w-3 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Public">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : source.is_shared_with_user ? (
            <svg className="h-3 w-3 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Shared">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
            </svg>
          ) : (
            <svg className="h-3 w-3 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Private">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          )}
          
          <button
            onClick={() => onToggleSource(source)}
            className="text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-200 transition-colors"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  )
}

// Source selector dropdown component
export const SourceSelectorDropdown = ({ 
  showSourceSelector, 
  availableSources, 
  selectedSources,
  onToggleSource,
  onClose,
  loading,
  className = ""
}) => {
  if (!showSourceSelector) return null

  // Calculate dynamic width based on longest source name
  const maxSourceNameLength = availableSources.reduce((max, source) => {
    const name = source.name || '[Unnamed Source]'
    return Math.max(max, name.length)
  }, 20) // Minimum width

  // Estimate width: roughly 8px per character + padding + icon space
  const estimatedWidth = Math.min(Math.max(maxSourceNameLength * 8 + 80, 200), 400)

  return (
    <div 
      data-source-selector="true"
      className={`absolute bottom-full left-0 mb-2 bg-gray-800 border border-gray-600 rounded-lg shadow-lg z-50 max-h-80 overflow-hidden ${className}`}
      style={{ width: `${estimatedWidth}px` }}
      onMouseDown={(e) => {
        e.preventDefault() // Prevent losing focus
      }}
    >
      <div className="p-3">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium text-gray-300">
            Select Sources ({selectedSources.length} selected)
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-300"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600"></div>
            <span className="ml-2 text-sm text-gray-400">Loading sources...</span>
          </div>
        ) : availableSources.length === 0 ? (
          <div className="text-center py-8 text-sm text-gray-400">
            No sources available
          </div>
        ) : (
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {availableSources.map((source) => {
              const isSelected = selectedSources.some(s => s.source_id === source.source_id)
              
              return (
                <div
                  key={source.source_id}
                  onClick={() => onToggleSource(source)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '8px 12px',
                    margin: '2px 0',
                    backgroundColor: isSelected ? '#4c1d95' : '#374151',
                    border: '1px solid #6b7280',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    style={{ marginRight: '8px' }}
                  />
                  
                  {/* Source Icon */}
                  <div className="w-6 h-6 bg-gradient-to-r from-blue-500 to-blue-600 rounded-md flex items-center justify-center flex-shrink-0 mr-2">
                    <svg className="h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  </div>

                  <div style={{ flex: 1 }}>
                    <span style={{ color: '#f3f4f6' }}>
                      {source.name || '[Unnamed Source]'}
                    </span>
                  </div>

                  {/* Source Type Indicator */}
                  <div className="flex items-center ml-2">
                    {source.is_public ? (
                      <svg className="h-4 w-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Public Source">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    ) : source.is_shared_with_user ? (
                      <svg className="h-4 w-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Shared with you">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
                      </svg>
                    ) : (
                      <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Private Source">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// Component to display sources used in a message
export const MessageSourcesUsed = ({ sources, className = "" }) => {
  if (!sources || sources.length === 0) return null

  return (
    <div className={`contents ${className}`}>
      {sources.map((source) => (
        <div
          key={source.source_id}
          className="inline-flex items-center space-x-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full text-xs border border-blue-200 dark:border-blue-800"
        >
          <div className="w-3 h-3 bg-gradient-to-r from-blue-500 to-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
            <svg className="h-1.5 w-1.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={4} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <span className="font-medium">{source.name}</span>
          
          {/* Source Type Indicator */}
          {source.is_public ? (
            <svg className="h-2 w-2 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Public">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : source.is_shared_with_user ? (
            <svg className="h-2 w-2 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Shared">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
            </svg>
          ) : (
            <svg className="h-2 w-2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" title="Private">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          )}
        </div>
      ))}
    </div>
  )
} 