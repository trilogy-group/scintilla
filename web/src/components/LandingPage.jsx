import React, { useState } from 'react'
import { Search, ArrowRight, MessageCircle, Settings, Bot, User } from 'lucide-react'
import { useBotAutoComplete, BotSuggestionsDropdown, SelectedBotsChips } from '../hooks/useBotAutoComplete.jsx'
import GoogleAuth from './GoogleAuth'

const LandingPage = ({ onSearch, onNavigate, isAuthenticated = false, currentUser = null }) => {
  const [query, setQuery] = useState('')

  // Bot auto-complete functionality
  const {
    selectedBots,
    showBotSuggestions,
    botSuggestions,
    selectedSuggestionIndex,
    inputRef,
    getBotSelectionData,
    handleInputChange,
    selectBotSuggestion,
    handleKeyDown,
    removeSelectedBot,
    clearSelectedBots,
    closeSuggestions
  } = useBotAutoComplete()

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!isAuthenticated || !query.trim()) return
    
    // Get clean message and selected bot IDs
    const { cleanMessage, botIds } = getBotSelectionData(query.trim())
    
    // Call the parent function to switch to chat mode and start the search
    onSearch(cleanMessage || query.trim(), { bot_ids: botIds })
    
    // Close suggestions and clear selections
    closeSuggestions()
  }

  const handleInputChangeWrapper = (e) => {
    handleInputChange(e, setQuery)
  }

  const handleKeyDownWrapper = (e) => {
    const result = handleKeyDown(e)
    if (result?.selectBot) {
      selectBotSuggestion(result.selectBot, query, setQuery)
    } else if (e.key === 'Enter' && !showBotSuggestions) {
      // If Enter is pressed and no bot suggestions are showing, submit the form
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleSelectBot = (bot) => {
    selectBotSuggestion(bot, query, setQuery)
  }

  const handleNavigation = (section) => {
    if (!isAuthenticated) {
      return // Don't allow navigation if not authenticated
    }
    
    if (onNavigate) {
      onNavigate(section)
    } else if (section === 'chat') {
      // Fallback to search callback for chat
      onSearch('')
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex flex-col">
      {/* Enhanced Header with Navigation */}
      <header className="px-8 py-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-8">
            <img 
              src="./img/scintilla_icon.svg" 
              alt="Scintilla" 
              className="h-8 w-8"
            />
            {isAuthenticated && (
              <nav className="hidden md:flex items-center space-x-6">
                <button
                  onClick={() => handleNavigation('chat')}
                  className="flex items-center space-x-2 text-gray-600 dark:text-gray-300 hover:text-scintilla-600 dark:hover:text-scintilla-400 transition-colors"
                >
                  <MessageCircle className="h-4 w-4" />
                  <span>Chat</span>
                </button>
                <button
                  onClick={() => handleNavigation('sources')}
                  className="flex items-center space-x-2 text-gray-600 dark:text-gray-300 hover:text-scintilla-600 dark:hover:text-scintilla-400 transition-colors"
                >
                  <Settings className="h-4 w-4" />
                  <span>Sources</span>
                </button>
                <button
                  onClick={() => handleNavigation('bots')}
                  className="flex items-center space-x-2 text-gray-600 dark:text-gray-300 hover:text-scintilla-600 dark:hover:text-scintilla-400 transition-colors"
                >
                  <Bot className="h-4 w-4" />
                  <span>Bots</span>
                </button>
              </nav>
            )}
          </div>
          
          {/* Right side - User info or IgniteTech branding */}
          <div className="flex items-center space-x-4">
            {isAuthenticated && currentUser ? (
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2">
                  {currentUser.picture_url ? (
                    <img 
                      src={currentUser.picture_url} 
                      alt={currentUser.name} 
                      className="h-8 w-8 rounded-full"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded-full bg-gray-300 flex items-center justify-center">
                      <User className="h-4 w-4 text-gray-600" />
                    </div>
                  )}
                  <div className="text-right">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      {currentUser.name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {currentUser.email}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Powered by IgniteTech
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main content - centered */}
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="w-full max-w-2xl text-center">
          
          {/* Show login form if not authenticated */}
          {!isAuthenticated ? (
            <GoogleAuth onAuthChange={() => {}} showOnlyLogin={true} />
          ) : (
            <>
              {/* Authenticated content - Scintilla Logo */}
              <div className="mb-8">
                <img 
                  src="./img/scintilla_logo.svg" 
                  alt="Scintilla" 
                  className="h-32 md:h-40 lg:h-48 mx-auto mb-4"
                />
                <p className="text-xl text-gray-600 dark:text-gray-300 mb-2">
                  Your intelligent search companion
                </p>
                <p className="text-base text-gray-500 dark:text-gray-400">
                  Ask questions and get answers from your knowledge base
                </p>
              </div>

              {/* Search Box with Bot Auto-complete */}
              <form onSubmit={handleSubmit} className="mb-6">
                {/* Selected Bots Chips */}
                <SelectedBotsChips 
                  selectedBots={selectedBots} 
                  onRemoveBot={removeSelectedBot}
                  className="justify-center" // Center the chips on landing page
                />
                
                <div className="relative">
                  <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={handleInputChangeWrapper}
                    onKeyDown={handleKeyDownWrapper}
                    placeholder="How may I help you today? (type @ to add bots)"
                    className="w-full px-8 py-6 text-lg border-2 border-gray-200 dark:border-gray-600 rounded-2xl focus:ring-4 focus:ring-scintilla-500/20 focus:border-scintilla-500 dark:bg-gray-800 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 shadow-lg transition-all duration-200"
                    autoFocus
                  />
                  
                  {/* Bot Suggestions Dropdown */}
                  <BotSuggestionsDropdown
                    showBotSuggestions={showBotSuggestions}
                    botSuggestions={botSuggestions}
                    selectedSuggestionIndex={selectedSuggestionIndex}
                    onSelectBot={handleSelectBot}
                    className="right-4" // Adjust positioning for landing page
                  />
                  
                  <div className="absolute right-4 top-1/2 transform -translate-y-1/2 flex items-center space-x-2">
                    <Search className="h-6 w-6 text-gray-400" />
                    {query.trim() && (
                      <button
                        type="submit"
                        className="p-2 bg-scintilla-500 text-white rounded-xl hover:bg-scintilla-600 transition-colors shadow-md"
                      >
                        <ArrowRight className="h-5 w-5" />
                      </button>
                    )}
                  </div>
                </div>
              </form>

              {/* Direct Chat Access */}
              <div className="mb-8">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  Or start a conversation without a specific question
                </p>
                <button
                  onClick={() => onSearch('')}
                  className="inline-flex items-center space-x-2 px-8 py-3 bg-scintilla-500 text-white text-lg font-medium rounded-xl hover:bg-scintilla-600 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  <span>Start Chatting</span>
                </button>
              </div>

              {/* Feature highlights */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
                <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
                  <div className="w-12 h-12 bg-scintilla-100 dark:bg-scintilla-900 rounded-lg flex items-center justify-center mx-auto mb-4">
                    <Search className="h-6 w-6 text-scintilla-600 dark:text-scintilla-400" />
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    Intelligent Search
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Find answers across all your connected sources and knowledge base
                  </p>
                </div>

                <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
                  <div className="w-12 h-12 bg-scintilla-100 dark:bg-scintilla-900 rounded-lg flex items-center justify-center mx-auto mb-4">
                    <svg className="h-6 w-6 text-scintilla-600 dark:text-scintilla-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    Conversational AI
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Have natural conversations and get contextual follow-up answers
                  </p>
                </div>

                <div className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700">
                  <div className="w-12 h-12 bg-scintilla-100 dark:bg-scintilla-900 rounded-lg flex items-center justify-center mx-auto mb-4">
                    <svg className="h-6 w-6 text-scintilla-600 dark:text-scintilla-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    Connected Sources
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Access information from multiple integrated sources and bots
                  </p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="px-8 py-6 text-center">
        <p className="text-xs text-gray-400 dark:text-gray-500">
          © 2025 IgniteTech. All rights reserved.
        </p>
      </footer>
    </div>
  )
}

export default LandingPage 