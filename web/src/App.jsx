import { useState, useEffect } from 'react'
import { Search, Send, Settings, User, BookOpen, Github, Code, Database, MessageSquare, AlertCircle, CheckCircle, RefreshCw, Bot, Server, Clock, Trash2 } from 'lucide-react'
import { useScintilla } from './hooks/useScintilla'
import CitationRenderer from './components/CitationRenderer'
import { SourcesManager } from './components/SourcesManager'
import { BotsManager } from './components/BotsManager'
import './App.css'
import api from './services/api'

function App() {
  const [query, setQuery] = useState('')
  const [currentView, setCurrentView] = useState('chat') // 'chat', 'sources', 'bots'
  const [conversations, setConversations] = useState([])
  const [conversationSearch, setConversationSearch] = useState('')
  
  const { 
    messages, 
    isLoading, 
    isConnected, 
    error,
    currentConversationId,
    sendMessage, 
    clearMessages,
    retryConnection,
    startNewConversation,
    loadConversation,
    setConversationCreatedCallback
  } = useScintilla()

  // Set up callback for when new conversations are created
  useEffect(() => {
    setConversationCreatedCallback((newConversationId) => {
      // Refresh conversations list when a new one is created
      console.log('New conversation created:', newConversationId, 'refreshing list')
      loadConversations()
    })
  }, [setConversationCreatedCallback])

  // Load previous conversations
  const loadConversations = async () => {
    try {
      console.log('Loading conversations...')
      const data = await api.getConversations()
      console.log('Loaded conversations:', data.length)
      setConversations(data)
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  }

  useEffect(() => {
    if (currentView === 'chat') {
      console.log('Chat view activated, loading conversations')
      loadConversations()
    }
  }, [currentView])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim() || isLoading) return

    await sendMessage(query, {
      mode: 'conversational',
      stream: true,
      use_user_sources: true
    })
    setQuery('')
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <img 
                src="/img/scintilla_icon.svg" 
                alt="Scintilla" 
                className="h-8 w-8"
              />
              <div>
                <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
                  Scintilla
                </h1>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Powered by IgniteTech
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {/* Navigation */}
              <nav className="flex items-center space-x-2">
                <button
                  onClick={() => setCurrentView('chat')}
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
                  onClick={() => setCurrentView('sources')}
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
                  onClick={() => setCurrentView('bots')}
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
              <button className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
                <Settings className="h-5 w-5" />
              </button>
              <button className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
                <User className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
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

      <div className="mx-auto px-4 sm:px-6 lg:px-8 py-8" style={{ maxWidth: 'min(100%, 1800px)' }}>
        {currentView === 'chat' ? (
          <div className="grid grid-cols-1 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4 lg:gap-8">
            {/* Sidebar - Previous Conversations */}
            <div className="lg:col-span-1 xl:col-span-1 2xl:col-span-1 space-y-6 order-2 lg:order-1">
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-700">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Recent Conversations</h3>
                    <button
                      onClick={startNewConversation}
                      className="text-xs px-3 py-1.5 bg-scintilla-500 hover:bg-scintilla-600 text-white rounded-md transition-colors font-medium"
                    >
                      New Chat
                    </button>
                  </div>
                </div>
                
                {/* Search Box */}
                <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                  <div className="relative">
                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search conversations..."
                      className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white placeholder-gray-400"
                    />
                  </div>
                </div>

                {/* Conversations List */}
                <div className={`overflow-y-auto transition-all duration-300 ${
                  messages.length === 0 
                    ? 'max-h-48 lg:max-h-[300px]' 
                    : messages.length <= 3 
                      ? 'max-h-48 lg:max-h-[400px]' 
                      : messages.length <= 6 
                        ? 'max-h-48 lg:max-h-[500px]' 
                        : messages.length <= 10 
                          ? 'max-h-48 lg:max-h-[600px]' 
                          : 'max-h-48 lg:max-h-[calc(100vh-500px)]'
                }`}>
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
                  ) : (
                    <div className="divide-y divide-gray-100 dark:divide-gray-700">
                      {conversations.map((conversation) => (
                        <div
                          key={conversation.conversation_id}
                          onClick={() => handleLoadConversation(conversation.conversation_id)}
                          className={`group relative px-4 py-4 cursor-pointer transition-all duration-200 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${
                            currentConversationId === conversation.conversation_id
                              ? 'bg-scintilla-50 dark:bg-scintilla-900/20 border-r-2 border-scintilla-500'
                              : ''
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0 pr-2">
                              <div className="flex items-center space-x-2 mb-1">
                                <h4 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                                  {conversation.title || 'Untitled Conversation'}
                                </h4>
                                {conversation.message_count && (
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
                            <button
                              onClick={(e) => deleteConversation(conversation.conversation_id, e)}
                              className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 transition-all rounded-md hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Main Chat Area */}
            <div className="lg:col-span-3 xl:col-span-4 2xl:col-span-5 order-1 lg:order-2">
              <div className={`bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col transition-all duration-300 max-w-4xl mx-auto ${
                messages.length === 0 
                  ? 'h-[400px]' 
                  : messages.length <= 3 
                    ? 'h-[500px]' 
                    : messages.length <= 6 
                      ? 'h-[600px]' 
                      : messages.length <= 10 
                        ? 'h-[700px]' 
                        : 'h-[calc(100vh-200px)] max-h-[800px]'
              }`}>
                {/* Chat Header */}
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <div className="flex items-center justify-between">
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
                          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 px-3 py-1 rounded-md border border-gray-300 dark:border-gray-600"
                        >
                          New Chat
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

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {messages.length === 0 ? (
                    <div className="text-center py-12">
                      <Search className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                      <p className="text-gray-500 dark:text-gray-400 text-lg">
                        Start a conversation to search your knowledge base
                      </p>
                      <p className="text-gray-400 dark:text-gray-500 text-sm mt-2">
                        I can help you find information across your sources and bots
                      </p>
                    </div>
                  ) : (
                    messages.map((message) => (
                      <div
                        key={message.id}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-xs lg:max-w-lg xl:max-w-2xl px-4 py-3 rounded-lg ${
                            message.role === 'user'
                              ? 'bg-scintilla-500 text-white'
                              : message.isError
                              ? 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-800'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                          }`}
                        >
                          <div className="relative">
                            {message.role === 'assistant' && message.sources && message.sources.length > 0 ? (
                              <CitationRenderer 
                                content={message.content}
                                sources={message.sources}
                                onCitationClick={(num) => console.log(`Citation ${num} clicked`)}
                              />
                            ) : (
                              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                            )}
                            {(message.isUsingTools || message.isProcessing) && (
                              <div className="flex items-center space-x-2 mt-2">
                                <div className="w-2 h-2 bg-scintilla-500 rounded-full animate-pulse"></div>
                                <span className="text-xs text-scintilla-600 dark:text-scintilla-400">
                                  {message.isUsingTools ? 'Executing tools...' : 'Processing results...'}
                                </span>
                              </div>
                            )}
                          </div>
                          {message.toolCalls && message.toolCalls.length > 0 && !message.isStreaming && (
                            <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                              <p className="text-xs text-gray-500 dark:text-gray-400">
                                Used {message.toolCalls.length} tool{message.toolCalls.length > 1 ? 's' : ''}: {message.toolCalls.map(tc => tc.name || tc).join(', ')}
                              </p>
                              {message.processingStats && (
                                <div className="mt-1 text-xs text-gray-400 dark:text-gray-500 space-y-1">
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
                                    <div className="inline-flex items-center space-x-1">
                                      <span>📚</span>
                                      <span>
                                        {message.processingStats.sources_found} source{message.processingStats.sources_found > 1 ? 's' : ''} referenced
                                      </span>
                                    </div>
                                  )}
                                </div>
                              )}
                              {message.queryTiming && (
                                <div className="mt-1 text-xs text-gray-400 dark:text-gray-500">
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
                          )}
                          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                            {formatTimestamp(message.timestamp)}
                          </p>
                        </div>
                      </div>
                    ))
                  )}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="bg-gray-100 dark:bg-gray-700 px-4 py-3 rounded-lg">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Input Area */}
                <div className="p-6 border-t border-gray-200 dark:border-gray-700">
                  <form onSubmit={handleSubmit} className="flex space-x-4">
                    <div className="flex-1 relative">
                      <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Ask to find answers from your knowledge base..."
                        className="w-full px-4 py-3 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
                        disabled={isLoading || !isConnected}
                      />
                      <Search className="absolute right-3 top-3.5 h-5 w-5 text-gray-400" />
                    </div>
                    <button
                      type="submit"
                      disabled={!query.trim() || isLoading || !isConnected}
                      className="px-6 py-3 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 focus:ring-2 focus:ring-scintilla-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <Send className="h-5 w-5" />
                    </button>
                  </form>
                </div>
              </div>
            </div>


          </div>
        ) : currentView === 'sources' ? (
          <div className="max-w-full">
            <SourcesManager />
          </div>
        ) : currentView === 'bots' ? (
          <div className="max-w-full">
            <BotsManager />
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default App
