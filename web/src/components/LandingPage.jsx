import React, { useState, useEffect } from 'react'
import { Search, ArrowRight } from 'lucide-react'
import { useBotAutoComplete, BotSuggestionsDropdown, SelectedBotsChips } from '../hooks/useBotAutoComplete.jsx'
import GoogleAuth from './GoogleAuth'

const LandingPage = ({ onSearch, onNavigate, isAuthenticated = false, currentUser = null, onAuthChange }) => {
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
    const { cleanMessage, botIds, selectedBots } = getBotSelectionData(query.trim())
    
    // Call the parent function to switch to chat mode and start the search
    onSearch(cleanMessage || query.trim(), { 
      bot_ids: botIds,
      selectedBots: selectedBots  // Also pass bot objects for display
    })
    
    // Clear the query input on landing page
    setQuery('')
    
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex flex-col">
      {/* Clean, Minimal Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Scintilla Branding - Far Left (match main app) */}
            <div className="flex items-center space-x-3">
              <button 
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
            
            {/* Right side - Auth Component (match main app structure) */}
            <div className="flex items-center space-x-4">
              <GoogleAuth onAuthChange={onAuthChange} />
            </div>
          </div>
        </div>
      </header>

      {/* Main content - centered */}
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="w-full max-w-2xl text-center">
          
          {/* Show login prompt if not authenticated */}
          {!isAuthenticated ? (
            <div className="mb-8">
              <img 
                src="./img/scintilla_logo.svg" 
                alt="Scintilla" 
                className="h-32 md:h-40 lg:h-48 mx-auto mb-6"
              />
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
                Welcome to Scintilla
              </h2>
              <p className="text-xl text-gray-600 dark:text-gray-300 mb-6">
                Your intelligent search companion
              </p>
              <p className="text-base text-gray-500 dark:text-gray-400 mb-8">
                Please sign in to access your knowledge base and start searching
              </p>
            </div>
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
                {/* Selected Bots Chips with Clear Button */}
                {selectedBots.length > 0 && (
                  <div className="flex items-center justify-center mb-4">
                    <div className="flex items-center space-x-4">
                      <SelectedBotsChips 
                        selectedBots={selectedBots} 
                        onRemoveBot={removeSelectedBot}
                        className="justify-center" // Center the chips on landing page
                      />
                      <button
                        onClick={clearSelectedBots}
                        className="px-3 py-1 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                      >
                        Clear Bots
                      </button>
                    </div>
                  </div>
                )}
                
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
                  className="inline-flex items-center space-x-2 px-8 py-3 bg-scintilla-500 text-white text-lg font-medium rounded-xl hover:bg-scintilla-600 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-1 hover:scale-105"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  <span>Start Chatting</span>
                </button>
              </div>

              {/* Feature highlights - Now functional navigation cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
                <button
                  onClick={() => onSearch('')}
                  className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 hover:shadow-xl hover:border-scintilla-200 dark:hover:border-scintilla-700 transition-all duration-200 group transform hover:-translate-y-1 hover:scale-105"
                >
                  <div className="w-12 h-12 bg-scintilla-100 dark:bg-scintilla-900 rounded-lg flex items-center justify-center mx-auto mb-4 group-hover:bg-scintilla-200 dark:group-hover:bg-scintilla-800 transition-colors">
                    <Search className="h-6 w-6 text-scintilla-600 dark:text-scintilla-400" />
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    Intelligent Search
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Find answers across all your connected sources and knowledge base
                  </p>
                  <div className="mt-3 text-xs text-scintilla-600 dark:text-scintilla-400 font-medium">
                    Start Chat →
                  </div>
                </button>

                <button
                  onClick={() => onNavigate ? onNavigate('sources') : onSearch('')}
                  className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 hover:shadow-xl hover:border-scintilla-200 dark:hover:border-scintilla-700 transition-all duration-200 group transform hover:-translate-y-1 hover:scale-105"
                >
                  <div className="w-12 h-12 bg-scintilla-100 dark:bg-scintilla-900 rounded-lg flex items-center justify-center mx-auto mb-4 group-hover:bg-scintilla-200 dark:group-hover:bg-scintilla-800 transition-colors">
                    <svg className="h-6 w-6 text-scintilla-600 dark:text-scintilla-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    Connected Sources
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Access information from multiple integrated sources and APIs
                  </p>
                  <div className="mt-3 text-xs text-scintilla-600 dark:text-scintilla-400 font-medium">
                    Manage Sources →
                  </div>
                </button>

                <button
                  onClick={() => onNavigate ? onNavigate('bots') : onSearch('')}
                  className="p-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 hover:shadow-xl hover:border-scintilla-200 dark:hover:border-scintilla-700 transition-all duration-200 group transform hover:-translate-y-1 hover:scale-105"
                >
                  <div className="w-12 h-12 bg-scintilla-100 dark:bg-scintilla-900 rounded-lg flex items-center justify-center mx-auto mb-4 group-hover:bg-scintilla-200 dark:group-hover:bg-scintilla-800 transition-colors">
                    <svg className="h-6 w-6 text-scintilla-600 dark:text-scintilla-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    Smart Bots
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Create specialized AI assistants with curated knowledge sources
                  </p>
                  <div className="mt-3 text-xs text-scintilla-600 dark:text-scintilla-400 font-medium">
                    Manage Bots →
                  </div>
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="px-4 sm:px-6 lg:px-8 py-6 text-center border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-400 dark:text-gray-500">
          © 2025 IgniteTech. All rights reserved.
        </p>
      </footer>
    </div>
  )
}

export default LandingPage 