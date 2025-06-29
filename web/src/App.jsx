import { useState, useEffect, useCallback, useRef } from 'react'
import { Search, Send, Settings, User, BookOpen, Github, Code, Database, MessageSquare, AlertCircle, CheckCircle, RefreshCw, Bot, Server, Clock, Trash2, Plus, Filter, X } from 'lucide-react'
import { useScintilla } from './hooks/useScintilla'
import { useAuth } from './hooks/useAuth'
import { useBotAutoComplete, BotSuggestionsDropdown, SelectedBotsChips } from './hooks/useBotAutoComplete.jsx'
import CitationRenderer from './components/CitationRenderer'
import { SourcesManager } from './components/SourcesManager'
import { BotsManager } from './components/BotsManager'
import LandingPage from './components/LandingPage'
import GoogleAuth from './components/GoogleAuth'
import { AgentTokensManager } from './components/AgentTokensManager'

import './App.css'
import api from './services/api'

function App() {
  const [query, setQuery] = useState('')
  const [currentView, setCurrentView] = useState('chat') // 'chat', 'sources', 'bots'
  const [showLanding, setShowLanding] = useState(true) // Show landing page initially
  const [showSettings, setShowSettings] = useState(false) // Settings modal
  const [conversations, setConversations] = useState([])
  const [conversationSearch, setConversationSearch] = useState('')
  const [isSearchFocused, setIsSearchFocused] = useState(false)
  const [searchSuggestions, setSearchSuggestions] = useState([])
  const [recentSearches, setRecentSearches] = useState(['xinet', 'scintilla architecture', 'bot configuration'])
  const searchInputRef = useRef(null)
  const messagesEndRef = useRef(null)
  
  // Authentication hook
  const { user: currentUser, isLoading: authLoading, isAuthenticated, handleAuthChange, requireAuth } = useAuth()
  
  // Update API service when auth changes
  useEffect(() => {
    const token = localStorage.getItem('scintilla_token')
    if (token && isAuthenticated) {
      api.setAuthToken(token)
    } else {
      api.clearAuthToken()
    }
  }, [isAuthenticated])
  
  // Bot auto-complete functionality
  const {
    selectedBots,
    showBotSuggestions,
    botSuggestions,
    selectedSuggestionIndex,
    inputRef,
    getBotSelectionData,
    handleInputChange: handleBotInputChange,
    selectBotSuggestion,
    handleKeyDown: handleBotKeyDown,
    removeSelectedBot,
    clearSelectedBots,
    closeSuggestions,
    loadBots: loadBotsForAutoComplete
  } = useBotAutoComplete()
  
  const { 
    messages, 
    isLoading, 
    isConnected, 
    error,
    currentConversationId,
    isSavingConversation,
    sendMessage, 
    clearMessages,
    retryConnection,
    startNewConversation,
    loadConversation,
    setConversationCreatedCallback
  } = useScintilla()

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Redirect to landing if not authenticated
  useEffect(() => {
    if (!authLoading && requireAuth(currentView)) {
      setShowLanding(true)
      setCurrentView('landing')
    }
    // Remove the automatic redirect for authenticated users - let them see landing page
  }, [authLoading, isAuthenticated, currentView, requireAuth])

  // Load previous conversations - but only when authenticated
  const loadConversations = useCallback(async () => {
    if (!isAuthenticated) {
      console.log('Skipping conversation load - not authenticated')
      return
    }
    
    try {
      console.log('Loading conversations...')
      const data = await api.getConversations()
      console.log('Loaded conversations:', data.length)
      setConversations(data)
    } catch (error) {
      console.error('Failed to load conversations:', error)
      // Don't show error for authentication failures during initial load
      if (error.message?.includes('401') || error.message?.includes('Unauthorized')) {
        console.log('Authentication required for conversations')
      }
    }
  }, [isAuthenticated])

  // Remove placeholder and refresh when real conversation is created
  const handleConversationCreated = useCallback((newConversationId) => {
    console.log('🎉 handleConversationCreated called with:', newConversationId)
    
    // Remove any placeholder conversations
    setConversations(prev => {
      const placeholders = prev.filter(conv => conv.isPlaceholder)
      console.log('🗑️ Removing placeholders:', placeholders.length)
      return prev.filter(conv => !conv.isPlaceholder)
    })
    
    // Refresh to get the real conversation data
    console.log('🔄 Refreshing conversations list...')
    loadConversations()
  }, [loadConversations])

  // Set up callback for when new conversations are created
  useEffect(() => {
    console.log('🔗 Setting up conversation created callback')
    setConversationCreatedCallback(handleConversationCreated)
  }, [setConversationCreatedCallback, handleConversationCreated])

  // Add placeholder conversation immediately when starting a new conversation
  const addPlaceholderConversation = (messageContent) => {
    console.log('🔄 addPlaceholderConversation called:', { messageContent, currentConversationId })
    
    if (currentConversationId) {
      console.log('❌ Skipping placeholder - conversation already exists:', currentConversationId)
      return // Only for new conversations
    }
    
    const placeholderConversation = {
      conversation_id: 'temp-' + Date.now(),
      title: messageContent.slice(0, 50) + (messageContent.length > 50 ? '...' : ''),
      last_message_preview: messageContent.slice(0, 100) + (messageContent.length > 100 ? '...' : ''),
      message_count: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      isPlaceholder: true
    }
    
    console.log('✅ Adding placeholder conversation:', placeholderConversation)
    
    // Add to the beginning of conversations list
    setConversations(prev => {
      console.log('📝 Previous conversations count:', prev.length)
      const newConversations = [placeholderConversation, ...prev]
      console.log('📝 New conversations count:', newConversations.length)
      return newConversations
    })
  }

  useEffect(() => {
    // Only load data when authenticated
    if (!isAuthenticated || authLoading) {
      console.log('Skipping data load - authentication not ready')
      return
    }
    
    // Always load bots for auto-complete (needed for landing page too)
    loadBotsForAutoComplete()
    
    // Skip other data loading if on landing page
    if (showLanding) {
      console.log('On landing page - bots loaded, skipping other data')
      return
    }
    
    if (currentView === 'chat') {
      console.log('Chat view activated, loading conversations')
      loadConversations()
    }
  }, [currentView, loadBotsForAutoComplete, loadConversations, isAuthenticated, authLoading, showLanding])

  // Handle input change for auto-complete
  const handleInputChange = (e) => {
    handleBotInputChange(e, setQuery)
  }

  // Handle bot suggestion selection
  const handleSelectBot = (bot) => {
    selectBotSuggestion(bot, query, setQuery)
  }

  // Handle keyboard navigation in suggestions
  const handleKeyDown = (e) => {
    const result = handleBotKeyDown(e)
    if (result?.selectBot) {
      selectBotSuggestion(result.selectBot, query, setQuery)
    } else if (e.key === 'Enter' && !showBotSuggestions) {
      // If Enter is pressed and no bot suggestions are showing, submit the form
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim() || isLoading || isSavingConversation) return

    // Get clean message and selected bot IDs
    const { cleanMessage, botIds } = getBotSelectionData(query.trim())
    const messageToSend = cleanMessage || query.trim()
    
    // Clear input and selected bots immediately for better UX
    setQuery('')
    clearSelectedBots()
    
    // Add placeholder conversation immediately if this is a new conversation
    addPlaceholderConversation(messageToSend)
    
    // Hide suggestions on submit
    closeSuggestions()

    // Send clean message + selected bot IDs
    await sendMessage(messageToSend, {
      mode: 'conversational',
      stream: true,
      use_user_sources: true,
      bot_ids: botIds
    })
  }

  const handleLoadConversation = async (conversationId) => {
    await loadConversation(conversationId)
  }

  const deleteConversation = async (conversationId, e) => {
    e.stopPropagation()
    
    // Optimistically remove from UI first
    const originalConversations = [...conversations]
    setConversations(conversations.filter(c => c.conversation_id !== conversationId))
    
    // If deleting current conversation, start new one
    if (currentConversationId === conversationId) {
      startNewConversation()
    }
    
    try {
      await api.deleteConversation(conversationId)
      console.log(`Successfully deleted conversation ${conversationId}`)
    } catch (error) {
      console.error('Failed to delete conversation:', error)
      // Restore conversations on error
      setConversations(originalConversations)
      // Show error message to user
      alert('Failed to delete conversation. Please try again.')
    }
  }

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  const formatConversationTime = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffTime = Math.abs(now - date)
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    
    if (diffDays === 1) return 'Today'
    if (diffDays === 2) return 'Yesterday'
    if (diffDays <= 7) return `${diffDays} days ago`
    return date.toLocaleDateString()
  }

  // Handle search input changes and generate suggestions
  const handleSearchChange = (e) => {
    const value = e.target.value
    setConversationSearch(value)
    
    if (value.trim()) {
      // Generate suggestions from conversation titles
      const suggestions = conversations
        .filter(conv => 
          conv.title && 
          conv.title.toLowerCase().includes(value.toLowerCase()) &&
          conv.title.toLowerCase() !== value.toLowerCase()
        )
        .slice(0, 5)
        .map(conv => conv.title)
      
      setSearchSuggestions(suggestions)
    } else {
      setSearchSuggestions([])
    }
  }

  // Handle search focus
  const handleSearchFocus = () => {
    setIsSearchFocused(true)
  }

  // Handle search blur
  const handleSearchBlur = () => {
    // Delay to allow clicking on suggestions
    setTimeout(() => setIsSearchFocused(false), 200)
  }

  // Handle suggestion click
  const handleSuggestionClick = (suggestion) => {
    setConversationSearch(suggestion)
    setIsSearchFocused(false)
    
    // Add to recent searches
    setRecentSearches(prev => {
      const filtered = prev.filter(s => s !== suggestion)
      return [suggestion, ...filtered].slice(0, 5)
    })
  }

  // Clear search
  const clearSearch = () => {
    setConversationSearch('')
    setSearchSuggestions([])
    setIsSearchFocused(false)
  }

  // Filter conversations based on search term
  const filteredConversations = conversations.filter(conversation => {
    if (!conversationSearch.trim()) return true
    
    const searchTerm = conversationSearch.toLowerCase()
    const title = (conversation.title || 'untitled conversation').toLowerCase()
    const preview = (conversation.last_message_preview || '').toLowerCase()
    
    return title.includes(searchTerm) || preview.includes(searchTerm)
  })

  // Handle search from landing page
  const handleLandingSearch = async (searchQuery, options = {}) => {
    setShowLanding(false) // Hide landing page
    setCurrentView('chat') // Switch to chat view
    setQuery(searchQuery) // Set the query
    
    // Always start a new conversation from landing page
    startNewConversation()
    
    // Start the search if there's a query
    if (searchQuery.trim()) {
      // Add placeholder conversation immediately
      addPlaceholderConversation(searchQuery)
      
      await sendMessage(searchQuery, {
        mode: 'conversational',
        stream: true,
        use_user_sources: true,
        bot_ids: options.bot_ids || []
      })
    }
  }

  // Enhanced auth change handler
  const handleAuthChangeWithTransition = (userData, token) => {
    console.log('Auth change detected:', { userData: !!userData, token: !!token })
    
    // Call the original auth change handler
    handleAuthChange(userData, token)
    
    // Don't automatically redirect after authentication - let user stay on landing page
    // They can navigate manually via the landing page interface
  }

  // Handle navigation from landing page
  const handleLandingNavigation = (section) => {
    if (!isAuthenticated) {
      // Don't allow navigation if not authenticated
      return
    }
    setShowLanding(false) // Hide landing page
    setCurrentView(section) // Switch to the requested view
  }

  // Handle navigation in header
  const handleViewChange = (view) => {
    if (!isAuthenticated && view !== 'landing') {
      // Redirect to landing if not authenticated
      setShowLanding(true)
      setCurrentView('landing')
      return
    }
    setCurrentView(view)
    if (view !== 'landing') {
      setShowLanding(false)
    }
  }

  // If landing page should be shown, render it
  if (showLanding) {
    return <LandingPage 
      onSearch={handleLandingSearch} 
      onNavigate={handleLandingNavigation} 
      isAuthenticated={isAuthenticated}
      currentUser={currentUser}
      onAuthChange={handleAuthChangeWithTransition}
    />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Scintilla Branding - Far Left */}
            <div className="flex items-center space-x-3">
              <button 
                onClick={() => setShowLanding(true)}
                className="flex items-center space-x-3 hover:opacity-75 transition-opacity"
              >
                <img 
                  src="./img/scintilla_icon.svg" 
                  alt="Scintilla" 
                  className="h-8 w-8"
                />
                <div>
                  <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Scintilla
                  </h1>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Powered by IgniteTech
                  </p>
                </div>
              </button>
            </div>
            
            {/* Navigation and Status - Right */}
            <div className="flex items-center space-x-4">
              {/* Navigation */}
              {isAuthenticated && (
                <nav className="flex items-center space-x-2">
                  <button
                    onClick={() => handleViewChange('chat')}
                    className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                      currentView === 'chat' 
                        ? 'bg-scintilla-100 dark:bg-scintilla-900 text-scintilla-700 dark:text-scintilla-300' 
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
                    }`}
                  >
                    <MessageSquare className="h-4 w-4" />
                    <span>Chat</span>
                  </button>
                  <button
                    onClick={() => handleViewChange('sources')}
                    className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                      currentView === 'sources' 
                        ? 'bg-scintilla-100 dark:bg-scintilla-900 text-scintilla-700 dark:text-scintilla-300' 
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
                    }`}
                  >
                    <Server className="h-4 w-4" />
                    <span>Sources</span>
                  </button>
                  <button
                    onClick={() => handleViewChange('bots')}
                    className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                      currentView === 'bots' 
                        ? 'bg-scintilla-100 dark:bg-scintilla-900 text-scintilla-700 dark:text-scintilla-300' 
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'
                    }`}
                  >
                    <Bot className="h-4 w-4" />
                    <span>Bots</span>
                  </button>
                </nav>
              )}

              {/* Connection Status */}
              <div className="flex items-center space-x-2">
                {isConnected ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                )}
                <span className={`text-xs ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
                {!isConnected && (
                  <button 
                    onClick={retryConnection}
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  >
                    <RefreshCw className="h-3 w-3" />
                  </button>
                )}
              </div>
              <button 
                onClick={() => setShowSettings(true)}
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                title="Settings"
              >
                <Settings className="h-5 w-5" />
              </button>
              <GoogleAuth onAuthChange={handleAuthChangeWithTransition} />
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
          <div className="px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-4 w-4 text-red-500" />
              <span className="text-sm text-red-700 dark:text-red-300">{error}</span>
              <button 
                onClick={retryConnection}
                className="text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 underline"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="h-[calc(100vh-64px)] flex">
        {currentView === 'chat' ? (
          <div className="flex w-full">
            {/* Sidebar - Previous Conversations */}
            <div className="w-80 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <div className="h-full flex flex-col">
                                {/* Header with Stacked Layout */}
                <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex-shrink-0">
                  <div className="space-y-3 h-16 flex flex-col justify-center">
                    {/* New Chat Button - Right Corner Above */}
                    <div className="flex justify-end">
                      <button
                        onClick={startNewConversation}
                        className="flex items-center space-x-1.5 text-xs px-2.5 py-1.5 bg-scintilla-500 hover:bg-scintilla-600 text-white rounded-md transition-colors font-medium"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        <span>New</span>
                      </button>
                    </div>
                    
                    {/* Full Width Search Box Below */}
                    <div className="relative">
                      <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                      <input
                        ref={searchInputRef}
                        type="text"
                        value={conversationSearch}
                        onChange={handleSearchChange}
                        onFocus={handleSearchFocus}
                        onBlur={handleSearchBlur}
                        placeholder="Search conversations..."
                        className={`w-full pl-9 pr-${conversationSearch ? '9' : '3'} py-2 text-sm border rounded-lg transition-all duration-200 focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white placeholder-gray-400 ${
                          isSearchFocused 
                            ? 'border-scintilla-300 dark:border-scintilla-600 shadow-md' 
                            : 'border-gray-200 dark:border-gray-600'
                        }`}
                      />
                      {conversationSearch && (
                        <button
                          onClick={clearSearch}
                          className="absolute right-3 top-2.5 h-4 w-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}

                      {/* Search Suggestions Dropdown */}
                      {isSearchFocused && (searchSuggestions.length > 0 || (!conversationSearch && recentSearches.length > 0)) && (
                        <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
                          {/* Recent Searches */}
                          {!conversationSearch && recentSearches.length > 0 && (
                            <div className="p-3 border-b border-gray-100 dark:border-gray-700">
                              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Recent Searches</p>
                              <div className="space-y-1">
                                {recentSearches.map((search, index) => (
                                  <button
                                    key={index}
                                    onClick={() => handleSuggestionClick(search)}
                                    className="flex items-center w-full px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md text-left"
                                  >
                                    <Clock className="h-3 w-3 text-gray-400 mr-2 flex-shrink-0" />
                                    <span className="truncate">{search}</span>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Conversation Suggestions */}
                          {searchSuggestions.length > 0 && (
                            <div className="p-3">
                              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Conversations</p>
                              <div className="space-y-1">
                                {searchSuggestions.map((suggestion, index) => (
                                  <button
                                    key={index}
                                    onClick={() => handleSuggestionClick(suggestion)}
                                    className="flex items-center w-full px-2 py-1.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md text-left"
                                  >
                                    <MessageSquare className="h-3 w-3 text-gray-400 mr-2 flex-shrink-0" />
                                    <span className="truncate">{suggestion}</span>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* No Results */}
                          {conversationSearch && searchSuggestions.length === 0 && (
                            <div className="p-3 text-center">
                              <p className="text-sm text-gray-500 dark:text-gray-400">No matching conversations</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                 </div>

                {/* Conversations List */}
                <div className="flex-1 overflow-y-auto">
                  {conversations.length === 0 ? (
                    <div className="text-center py-12 px-4">
                      <MessageSquare className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                        No conversations yet
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500">
                        Start chatting to see your history here
                      </p>
                    </div>
                  ) : filteredConversations.length === 0 ? (
                    <div className="text-center py-12 px-4">
                      <Search className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                      <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                        No conversations found
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500">
                        Try adjusting your search term
                      </p>
                    </div>
                  ) : (
                    <div className="divide-y divide-gray-100 dark:divide-gray-700">
                      {filteredConversations.map((conversation) => (
                        <div
                          key={conversation.conversation_id}
                          onClick={() => !conversation.isPlaceholder && handleLoadConversation(conversation.conversation_id)}
                          className={`group relative px-4 py-4 transition-all duration-200 ${
                            conversation.isPlaceholder 
                              ? 'cursor-default opacity-75' 
                              : 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50'
                          } ${
                            currentConversationId === conversation.conversation_id
                              ? 'bg-scintilla-50 dark:bg-scintilla-900/20 border-r-2 border-scintilla-500'
                              : ''
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0 pr-2">
                              <div className="flex items-center space-x-2 mb-1">
                                <h4 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                                  {conversation.isPlaceholder 
                                    ? 'New Conversation' 
                                    : (conversation.title || 'Untitled Conversation')
                                  }
                                </h4>
                                {conversation.isPlaceholder && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-scintilla-100 dark:bg-scintilla-900 text-scintilla-700 dark:text-scintilla-300">
                                    Writing...
                                  </span>
                                )}
                                {conversation.message_count && !conversation.isPlaceholder && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                                    {conversation.message_count}
                                  </span>
                                )}
                              </div>
                              {conversation.last_message_preview && (
                                <p className="text-xs text-gray-500 dark:text-gray-400 truncate mb-2">
                                  {conversation.last_message_preview}
                                </p>
                              )}
                              <div className="flex items-center space-x-2">
                                <span className="text-xs text-gray-400 dark:text-gray-500">
                                  {formatConversationTime(conversation.updated_at)}
                                </span>
                                {currentConversationId === conversation.conversation_id && (
                                  <span className="inline-flex items-center text-xs text-scintilla-600 dark:text-scintilla-400">
                                    <div className="w-1.5 h-1.5 bg-scintilla-500 rounded-full mr-1"></div>
                                    Active
                                  </span>
                                )}
                              </div>
                            </div>
                            {!conversation.isPlaceholder && (
                              <button
                                onClick={(e) => deleteConversation(conversation.conversation_id, e)}
                                className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 transition-all rounded-md hover:bg-gray-100 dark:hover:bg-gray-600"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col bg-white dark:bg-gray-800">
              {/* Chat Header */}
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
                <div className="flex items-center justify-between h-16">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-gradient-to-r from-scintilla-500 to-scintilla-600 rounded-full flex items-center justify-center">
                      <MessageSquare className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {currentConversationId ? 'Continue Conversation' : 'How may I help you today?'}
                      </h2>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        Ask to find answers from your knowledge base
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {currentConversationId && (
                      <button 
                        onClick={startNewConversation}
                        className="flex items-center space-x-1.5 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 px-3 py-1 rounded-md border border-gray-300 dark:border-gray-600"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        <span>New Chat</span>
                      </button>
                    )}
                    {messages.length > 0 && (
                      <button 
                        onClick={clearMessages}
                        className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Messages Area - Center-aligned like Dashworks */}
              <div className="flex-1 overflow-y-auto px-6 py-4">
                <div className="max-w-4xl mx-auto space-y-8">
                  {messages.length === 0 ? (
                    <div className="text-center py-20">
                      <Search className="h-16 w-16 text-gray-300 dark:text-gray-600 mx-auto mb-6" />
                      <p className="text-gray-500 dark:text-gray-400 text-xl mb-2">
                        Start a conversation to search your knowledge base
                      </p>
                      <p className="text-gray-400 dark:text-gray-500 text-base">
                        I can help you find information across your sources and bots
                      </p>
                    </div>
                  ) : (
                    messages.map((message) => (
                      <div key={message.id} className="w-full">
                        {message.role === 'user' ? (
                        /* User Message - Boxed and full width */
                        <div className="w-full">
                          <div className="bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 px-6 py-4 rounded-2xl shadow-sm">
                            <p className="whitespace-pre-wrap leading-relaxed text-gray-900 dark:text-white">{message.content}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                              {formatTimestamp(message.timestamp)}
                            </p>
                          </div>
                        </div>
                      ) : (
                        /* AI Response - Free-flowing and center-aligned */
                        <div className="w-full">
                          <div className={`mx-auto ${
                            message.isError
                              ? 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800 px-6 py-4 rounded-2xl max-w-2xl'
                              : 'text-gray-900 dark:text-white'
                          }`}>
                            <div className="relative group">
                              {/* Copy button - only show for assistant messages */}
                              {message.role === 'assistant' && !message.isError && (
                                <button
                                  onClick={(event) => {
                                    // Extract plain text from content, removing citations and formatting
                                    const plainText = message.content
                                      .replace(/\[(\d+)\]/g, '') // Remove citation numbers
                                      .replace(/\*\*([^*]+)\*\*/g, '$1') // Remove bold formatting
                                      .replace(/\*([^*]+)\*/g, '$1') // Remove italic formatting
                                      .replace(/#{1,6}\s+/g, '') // Remove markdown headers
                                      .replace(/^\s*[-*+]\s+/gm, '• ') // Convert bullet points
                                      .replace(/^\s*\d+\.\s+/gm, (match) => {
                                        const num = match.match(/\d+/)[0]
                                        return `${num}. `
                                      }) // Keep numbered lists
                                      .trim()
                                    
                                    const button = event.target.closest('button')
                                    const originalText = button.innerHTML
                                    
                                    // Function to show success feedback
                                    const showSuccess = () => {
                                      button.innerHTML = '✓ Copied!'
                                      button.classList.add('bg-green-100', 'text-green-700')
                                      setTimeout(() => {
                                        button.innerHTML = originalText
                                        button.classList.remove('bg-green-100', 'text-green-700')
                                      }, 2000)
                                    }
                                    
                                    // Function to show error feedback
                                    const showError = () => {
                                      button.innerHTML = '❌ Failed'
                                      button.classList.add('bg-red-100', 'text-red-700')
                                      setTimeout(() => {
                                        button.innerHTML = originalText
                                        button.classList.remove('bg-red-100', 'text-red-700')
                                      }, 2000)
                                    }
                                    
                                    // Try modern clipboard API first
                                    if (navigator.clipboard && navigator.clipboard.writeText) {
                                      navigator.clipboard.writeText(plainText)
                                        .then(showSuccess)
                                        .catch(() => {
                                          // Fallback to legacy method
                                          try {
                                            const textArea = document.createElement('textarea')
                                            textArea.value = plainText
                                            textArea.style.position = 'fixed'
                                            textArea.style.left = '-999999px'
                                            textArea.style.top = '-999999px'
                                            document.body.appendChild(textArea)
                                            textArea.focus()
                                            textArea.select()
                                            const successful = document.execCommand('copy')
                                            document.body.removeChild(textArea)
                                            if (successful) {
                                              showSuccess()
                                            } else {
                                              showError()
                                            }
                                          } catch {
                                            showError()
                                          }
                                        })
                                    } else {
                                      // Use legacy method directly
                                      try {
                                        const textArea = document.createElement('textarea')
                                        textArea.value = plainText
                                        textArea.style.position = 'fixed'
                                        textArea.style.left = '-999999px'
                                        textArea.style.top = '-999999px'
                                        document.body.appendChild(textArea)
                                        textArea.focus()
                                        textArea.select()
                                        const successful = document.execCommand('copy')
                                        document.body.removeChild(textArea)
                                        if (successful) {
                                          showSuccess()
                                        } else {
                                          showError()
                                        }
                                      } catch {
                                        showError()
                                      }
                                    }
                                  }}
                                  className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300 px-3 py-1 rounded-md text-sm border border-gray-200 dark:border-gray-600"
                                  title="Copy response text"
                                >
                                  📋 Copy
                                </button>
                              )}
                              
                              {message.role === 'assistant' ? (
                                <CitationRenderer 
                                  content={message.content}
                                  sources={message.sources || []}
                                  onCitationClick={(num) => console.log(`Citation ${num} clicked`)}
                                />
                              ) : (
                                <div className="prose prose-lg dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:mb-4">
                                  <div className="whitespace-pre-wrap leading-relaxed text-base">{message.content}</div>
                                </div>
                              )}
                              {(message.isUsingTools || message.isProcessing) && (
                                <div className="flex items-center justify-center space-x-2 mt-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                  <div className="w-2 h-2 bg-scintilla-500 rounded-full animate-pulse"></div>
                                  <span className="text-sm text-scintilla-600 dark:text-scintilla-400">
                                    {message.isUsingTools ? 'Executing tools...' : 'Processing results...'}
                                  </span>
                                </div>
                              )}
                            </div>
                            {message.toolCalls && message.toolCalls.length > 0 && !message.isStreaming && (
                              <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-600">
                                <div className="text-center">
                                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                                    Used {message.toolCalls.length} tool{message.toolCalls.length > 1 ? 's' : ''}: {message.toolCalls.map(tc => tc.name || tc).join(', ')}
                                  </p>
                                  {message.processingStats && (
                                    <div className="text-sm text-gray-400 dark:text-gray-500 space-y-1">
                                      {message.processingStats.tools_truncated > 0 && (
                                        <div className="inline-flex items-center space-x-1">
                                          <span>📊</span>
                                          <span>
                                            Content optimized: {message.processingStats.tokens_saved?.toLocaleString()} tokens saved
                                            ({message.processingStats.tools_truncated} tool{message.processingStats.tools_truncated > 1 ? 's' : ''} processed)
                                          </span>
                                        </div>
                                      )}
                                      {message.processingStats.sources_found > 0 && (
                                        <div className="inline-flex items-center space-x-1 ml-4">
                                          <span>📚</span>
                                          <span>
                                            {message.processingStats.sources_found} source{message.processingStats.sources_found > 1 ? 's' : ''} referenced
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                  {message.queryTiming && (
                                    <div className="mt-2 text-sm text-gray-400 dark:text-gray-500">
                                      <div className="inline-flex items-center space-x-1">
                                        <span>⏱️</span>
                                        <span>
                                          Query completed in {message.queryTiming.totalTime}ms
                                          {message.queryTiming.toolsExecutionTime && ` (tools: ${message.queryTiming.toolsExecutionTime}ms)`}
                                          {message.queryTiming.backendTiming && ` (backend: ${message.queryTiming.backendTiming.total_time_ms}ms)`}
                                        </span>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                            <div className="text-center mt-4">
                              <p className="text-xs text-gray-400 dark:text-gray-500">
                                {formatTimestamp(message.timestamp)}
                              </p>
                            </div>
                          </div>
                        </div>
                                              )}
                      </div>
                    ))
                  )}
                  {isLoading && (
                    <div className="flex justify-center">
                      <div className="bg-gray-50 dark:bg-gray-700 px-6 py-4 rounded-2xl">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                  {/* Scroll target */}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* Input Area */}
              <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
                {/* Selected Bots Chips */}
                <SelectedBotsChips 
                  selectedBots={selectedBots} 
                  onRemoveBot={removeSelectedBot}
                />
                
                <form onSubmit={handleSubmit} className="flex space-x-4">
                  <div className="flex-1 relative">
                    <input
                      type="text"
                      value={query}
                      onChange={handleInputChange}
                      onKeyDown={handleKeyDown}
                      placeholder={
                        isSavingConversation 
                          ? "Saving conversation..." 
                          : "Ask to find answers from your knowledge base... (type @ to add bots)"
                      }
                      className="w-full px-6 py-4 pr-12 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 text-base"
                      disabled={isLoading || !isConnected || isSavingConversation}
                      ref={inputRef}
                    />
                    <Search className="absolute right-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                    
                    {/* Bot Suggestions Dropdown */}
                    <BotSuggestionsDropdown
                      showBotSuggestions={showBotSuggestions}
                      botSuggestions={botSuggestions}
                      selectedSuggestionIndex={selectedSuggestionIndex}
                      onSelectBot={handleSelectBot}
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={!query.trim() || isLoading || !isConnected || isSavingConversation}
                    className="px-6 py-4 bg-scintilla-500 text-white rounded-xl hover:bg-scintilla-600 focus:ring-2 focus:ring-scintilla-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <Send className="h-5 w-5" />
                  </button>
                </form>
              </div>
            </div>
          </div>
        ) : currentView === 'sources' ? (
          <div className="flex-1 p-8">
            <div className="max-w-5xl mx-auto">
              <SourcesManager />
            </div>
          </div>
        ) : currentView === 'bots' ? (
          <div className="flex-1 p-8">
            <div className="max-w-5xl mx-auto">
              <BotsManager />
            </div>
          </div>
        ) : null}
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center">
                <Settings className="h-6 w-6 mr-2 text-scintilla-600" />
                Settings
              </h2>
              <button
                onClick={() => setShowSettings(false)}
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
              <AgentTokensManager />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
