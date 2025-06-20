import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../services/api'

export const useBotAutoComplete = () => {
  // Bot auto-complete state
  const [bots, setBots] = useState([])
  const [selectedBots, setSelectedBots] = useState([]) // Array of selected bot objects
  const [showBotSuggestions, setShowBotSuggestions] = useState(false)
  const [botSuggestions, setBotSuggestions] = useState([])
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1)
  const [mentionStartPos, setMentionStartPos] = useState(-1)
  const inputRef = useRef(null)

  // Load bots for auto-complete
  const loadBots = useCallback(async () => {
    try {
      const data = await api.getBots()
      setBots(data)
    } catch (error) {
      console.error('Failed to load bots:', error)
    }
  }, [])

  // Load bots when hook is first used
  useEffect(() => {
    loadBots()
  }, [loadBots])

  // Close suggestions when clicking outside (but not on the dropdown itself)
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (inputRef.current && !inputRef.current.contains(event.target)) {
        // Check if click is on the dropdown
        const dropdown = document.querySelector('[data-bot-dropdown="true"]')
        if (dropdown && dropdown.contains(event.target)) {
          return
        }
        
        setShowBotSuggestions(false)
        setBotSuggestions([])
        setSelectedSuggestionIndex(-1)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  // Add a bot to selection
  const addSelectedBot = useCallback((bot) => {
    setSelectedBots(prev => {
      // Check if bot is already selected
      if (prev.find(b => b.bot_id === bot.bot_id)) {
        return prev
      }
      return [...prev, bot]
    })
  }, [])

  // Remove a bot from selection
  const removeSelectedBot = useCallback((botId) => {
    setSelectedBots(prev => prev.filter(bot => bot.bot_id !== botId))
  }, [])

  // Clear all selected bots
  const clearSelectedBots = useCallback(() => {
    setSelectedBots([])
  }, [])

  // Get bot IDs and clean message (no need to parse text anymore)
  const getBotSelectionData = useCallback((message) => {
    return {
      cleanMessage: message.trim(), // No @mentions to clean
      botIds: selectedBots.map(bot => bot.bot_id),
      selectedBots
    }
  }, [selectedBots])

  // Handle input change for auto-complete (now only triggers on @)
  const handleInputChange = useCallback((e, onQueryChange) => {
    const value = e.target.value
    const cursorPosition = e.target.selectionStart
    onQueryChange(value)

    // Check for @mentions to trigger bot suggestions
    const textBeforeCursor = value.substring(0, cursorPosition)
    const mentionMatch = textBeforeCursor.match(/@(\w*)$/)
    
    if (mentionMatch) {
      const searchTerm = mentionMatch[1].toLowerCase()
      
      // Filter out already selected bots
      const availableBots = bots.filter(bot => 
        !selectedBots.find(selected => selected.bot_id === bot.bot_id)
      )
      const filteredBots = availableBots.filter(bot => 
        bot.name.toLowerCase().includes(searchTerm)
      )
      
      setBotSuggestions(filteredBots)
      setMentionStartPos(mentionMatch.index)
      setShowBotSuggestions(filteredBots.length > 0)
      setSelectedSuggestionIndex(filteredBots.length > 0 ? 0 : -1) // Auto-select first item
    } else {
      setShowBotSuggestions(false)
      setBotSuggestions([])
      setMentionStartPos(-1)
    }
  }, [bots, selectedBots])

  // Handle bot suggestion selection (now adds to chips instead of text)
  const selectBotSuggestion = useCallback((bot, currentQuery, onQueryChange) => {
    // Add bot to selection chips
    addSelectedBot(bot)
    
    // Remove the @mention text from input if we have a valid position
    let newQuery = currentQuery
    if (mentionStartPos >= 0) {
      const beforeMention = currentQuery.substring(0, mentionStartPos)
      const afterCursor = currentQuery.substring(inputRef.current?.selectionStart || currentQuery.length)
      newQuery = `${beforeMention}${afterCursor}`.trim()
    }
    
    onQueryChange(newQuery)
    setShowBotSuggestions(false)
    setBotSuggestions([])
    setMentionStartPos(-1)
    setSelectedSuggestionIndex(-1)
    
    // Focus back to input
    setTimeout(() => {
      if (inputRef.current) {
        const newCursorPos = mentionStartPos >= 0 ? mentionStartPos : newQuery.length
        inputRef.current.focus()
        inputRef.current.setSelectionRange(newCursorPos, newCursorPos)
      }
    }, 10) // Slightly longer delay to ensure the dropdown closes first
  }, [mentionStartPos, addSelectedBot])

  // Handle keyboard navigation in suggestions
  const handleKeyDown = useCallback((e) => {
    if (!showBotSuggestions || botSuggestions.length === 0) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedSuggestionIndex(prev => 
          prev < botSuggestions.length - 1 ? prev + 1 : 0
        )
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedSuggestionIndex(prev => 
          prev > 0 ? prev - 1 : botSuggestions.length - 1
        )
        break
      case 'Enter':
        if (selectedSuggestionIndex >= 0 && botSuggestions[selectedSuggestionIndex]) {
          e.preventDefault()
          return { selectBot: botSuggestions[selectedSuggestionIndex] }
        }
        break
      case 'Escape':
        e.preventDefault()
        setShowBotSuggestions(false)
        setBotSuggestions([])
        setSelectedSuggestionIndex(-1)
        break
    }
    return null
  }, [showBotSuggestions, botSuggestions, selectedSuggestionIndex])

  // Close suggestions helper
  const closeSuggestions = useCallback(() => {
    setShowBotSuggestions(false)
    setBotSuggestions([])
    setSelectedSuggestionIndex(-1)
  }, [])

  return {
    // State
    bots,
    selectedBots,
    showBotSuggestions,
    botSuggestions,
    selectedSuggestionIndex,
    inputRef,

    // Functions
    loadBots,
    addSelectedBot,
    removeSelectedBot,
    clearSelectedBots,
    getBotSelectionData,
    handleInputChange,
    selectBotSuggestion,
    handleKeyDown,
    closeSuggestions
  }
}

// Selected bots chips component
export const SelectedBotsChips = ({ selectedBots, onRemoveBot, className = "" }) => {
  if (selectedBots.length === 0) return null

  return (
    <div className={`flex flex-wrap gap-2 mb-3 ${className}`}>
      {selectedBots.map((bot) => (
        <div
          key={bot.bot_id}
          className="inline-flex items-center space-x-2 bg-scintilla-100 dark:bg-scintilla-900/50 text-scintilla-700 dark:text-scintilla-300 px-3 py-1.5 rounded-full text-sm border border-scintilla-200 dark:border-scintilla-800"
        >
          <div className="w-4 h-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
            <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <span className="font-medium">@{bot.name}</span>
          <button
            onClick={() => onRemoveBot(bot.bot_id)}
            className="text-scintilla-500 hover:text-scintilla-700 dark:text-scintilla-400 dark:hover:text-scintilla-200 transition-colors"
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

// Bot suggestions dropdown component
export const BotSuggestionsDropdown = ({ 
  showBotSuggestions, 
  botSuggestions, 
  selectedSuggestionIndex, 
  onSelectBot,
  className = ""
}) => {
  if (!showBotSuggestions) return null

  const handleBotClick = (e, bot, index) => {
    e.preventDefault()
    e.stopPropagation()
    onSelectBot(bot)
  }

  const handleMouseEnter = (index) => {
    // Don't update selection index on mouse hover to avoid conflicts with keyboard navigation
  }

  return (
    <div 
      data-bot-dropdown="true"
      className={`absolute bottom-full left-0 right-12 mb-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto ${className}`}
      onMouseDown={(e) => {
        e.preventDefault() // Prevent input from losing focus
      }}
    >
      <div className="p-2">
        <div className="text-xs text-gray-500 dark:text-gray-400 px-3 py-2 border-b border-gray-100 dark:border-gray-600">
          Select a bot to add:
        </div>
        {botSuggestions.length === 0 ? (
          <div className="px-3 py-4 text-sm text-gray-500 dark:text-gray-400 text-center">
            No more bots available
          </div>
        ) : (
          botSuggestions.map((bot, index) => (
            <div
              key={bot.bot_id}
              onClick={(e) => handleBotClick(e, bot, index)}
              onMouseEnter={() => handleMouseEnter(index)}
              className={`flex items-center space-x-3 px-3 py-2 cursor-pointer rounded-md transition-colors ${
                index === selectedSuggestionIndex
                  ? 'bg-scintilla-100 dark:bg-scintilla-900/50 text-scintilla-700 dark:text-scintilla-300 ring-1 ring-scintilla-300 dark:ring-scintilla-700'
                  : 'hover:bg-gray-50 dark:hover:bg-gray-600 text-gray-900 dark:text-white'
              }`}
            >
              <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  @{bot.name}
                </div>
                {bot.description && (
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {bot.description}
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-400 dark:text-gray-500">
                {bot.sources?.length || 0} sources
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
} 