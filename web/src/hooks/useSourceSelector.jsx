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
    closeSelector
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
          className="inline-flex items-center space-x-2 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 px-3 py-1.5 rounded-full text-sm border border-purple-200 dark:border-purple-800"
        >
          <div className="w-4 h-4 bg-gradient-to-r from-purple-500 to-indigo-600 rounded-full flex items-center justify-center flex-shrink-0">
            <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <span className="font-medium">{source.name}</span>
          <button
            onClick={() => onToggleSource(source)}
            className="text-purple-500 hover:text-purple-700 dark:text-purple-400 dark:hover:text-purple-200 transition-colors"
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

  return (
    <div 
      data-source-selector="true"
      className={`absolute bottom-full left-0 right-0 mb-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg z-50 max-h-80 overflow-hidden ${className}`}
      onMouseDown={(e) => {
        e.preventDefault() // Prevent losing focus
      }}
    >
      <div className="p-3">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Select Sources ({selectedSources.length} selected)
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600"></div>
            <span className="ml-2 text-sm text-gray-500">Loading sources...</span>
          </div>
        ) : availableSources.length === 0 ? (
          <div className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">
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
                  className={`flex items-center space-x-3 px-3 py-2 cursor-pointer rounded-md transition-colors ${
                    isSelected
                      ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-600 text-gray-900 dark:text-white'
                  }`}
                >
                  <div className="flex-shrink-0">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}} // Handled by parent click
                      className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                  </div>
                  
                  <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-indigo-600 rounded-full flex items-center justify-center flex-shrink-0">
                    <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">
                      {source.name}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {source.owner_type === 'user' 
                        ? source.is_shared_with_user 
                          ? 'Shared with you' 
                          : source.is_public 
                            ? 'Public source' 
                            : 'Your source'
                        : 'Bot source'
                      } • {source.cached_tool_count || 0} tools
                    </div>
                  </div>
                  
                  {source.tools_cache_status && (
                    <div className="flex-shrink-0">
                      <div className={`w-2 h-2 rounded-full ${
                        source.tools_cache_status === 'cached' ? 'bg-green-500' :
                        source.tools_cache_status === 'pending' ? 'bg-yellow-500' :
                        source.tools_cache_status === 'error' ? 'bg-red-500' :
                        'bg-gray-400'
                      }`} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
} 