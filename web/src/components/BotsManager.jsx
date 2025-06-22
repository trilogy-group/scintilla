import { useState, useEffect } from 'react'
import { Bot, Users, Globe, Lock, Plus, Settings, Eye, Loader, AlertCircle, Edit2, Trash2, X, RefreshCw, CheckCircle, ChevronDown, ChevronRight, Wrench, Clock, AlertTriangle } from 'lucide-react'
import api from '../services/api'

export const BotsManager = () => {
  const [bots, setBots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [botSources, setBotSources] = useState({})
  const [selectedBot, setSelectedBot] = useState(null)
  const [showBotDetails, setShowBotDetails] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showEditForm, setShowEditForm] = useState(false)
  const [editingBot, setEditingBot] = useState(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [refreshingSourceId, setRefreshingSourceId] = useState(null)
  const [expandedTools, setExpandedTools] = useState({}) // Track which source tools are expanded

  // Form state for creating/editing bots
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    sources: [],
    is_public: false,
    allowed_user_ids: []
  })

  // Source form state
  const [currentSource, setCurrentSource] = useState({
    name: '',
    description: '',
    instructions: '',
    server_url: '',
    auth_method: 'headers',
    auth_headers: '',
    credentials: {}
  })

  // Authentication method configurations (simplified)
  const AUTH_METHODS = {
    headers: {
      label: 'Header-based Authentication',
      description: 'Use custom headers (Authorization, X-API-Key, etc.)',
      placeholder: '{"Authorization": "Bearer your-token", "X-API-Key": "your-key"}'
    },
    url_embedded: {
      label: 'URL-embedded Authentication', 
      description: 'API key/credentials embedded in the URL',
      placeholder: 'https://server.com/sse?x-api-key=your-key&other=params'
    }
  }

  // Handle auth method change - reset credentials
  const handleAuthMethodChange = (newMethod) => {
    setCurrentSource({
      ...currentSource,
      auth_method: newMethod,
      auth_headers: '',
      server_url: ''
    })
  }

  const [showSourceForm, setShowSourceForm] = useState(false)

  // Tool status helper functions (same as SourcesManager)
  const getToolStatusColor = (status) => {
    switch (status) {
      case 'cached':
        return 'text-green-600 dark:text-green-400'
      case 'caching':
        return 'text-blue-600 dark:text-blue-400'
      case 'pending':
        return 'text-yellow-600 dark:text-yellow-400'
      case 'error':
        return 'text-red-600 dark:text-red-400'
      default:
        return 'text-gray-500 dark:text-gray-400'
    }
  }

  const getToolStatusIcon = (status) => {
    switch (status) {
      case 'cached':
        return <CheckCircle className="h-4 w-4" />
      case 'caching':
        return <Loader className="h-4 w-4 animate-spin" />
      case 'pending':
        return <Clock className="h-4 w-4" />
      case 'error':
        return <AlertTriangle className="h-4 w-4" />
      default:
        return <Wrench className="h-4 w-4" />
    }
  }

  const toggleToolsExpansion = (sourceId) => {
    setExpandedTools(prev => ({
      ...prev,
      [sourceId]: !prev[sourceId]
    }))
  }

  useEffect(() => {
    loadBots()
    checkAdminStatus()
  }, [])

  const checkAdminStatus = async () => {
    try {
      // For now, we'll assume the user is admin since we're using mock auth
      // In production, this would check the user's actual admin status from the API
      setIsAdmin(true)
    } catch (err) {
      console.error('Failed to check admin status:', err)
      setIsAdmin(false)
    }
  }

  const loadBots = async () => {
    try {
      setLoading(true)
      const botsData = await api.getBots()
      setBots(botsData)
      setError(null)
      
      // Load source details for each bot
      const sourcesData = {}
      for (const bot of botsData) {
        try {
          const botDetails = await api.getBot(bot.bot_id)
          sourcesData[bot.bot_id] = botDetails.sources || []
        } catch (err) {
          console.error(`Failed to load sources for bot ${bot.bot_id}:`, err)
          sourcesData[bot.bot_id] = []
        }
      }
      setBotSources(sourcesData)
    } catch (err) {
      setError('Failed to load bots: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const resetForms = () => {
    setFormData({
      name: '',
      description: '',
      sources: [],
      is_public: false,
      allowed_user_ids: []
    })
    setCurrentSource({
      name: '',
      description: '',
      instructions: '',
      server_url: '',
      auth_method: 'headers',
      auth_headers: '',
      credentials: {}
    })
    setShowSourceForm(false)
  }

  const handleCreateBot = async (e) => {
    e.preventDefault()
    try {
      // Sources are already processed in handleAddSource, just use them directly
      const botData = {
        ...formData,
        sources: formData.sources
      }

      await api.createBot(botData)
      setShowCreateForm(false)
      resetForms()
      await loadBots()
    } catch (err) {
      setError('Failed to create bot: ' + err.message)
    }
  }

  const handleEditBot = async (e) => {
    e.preventDefault()
    try {
      // Format sources for the API (simplified)
      const formattedSources = formData.sources.map(source => ({
        source_id: source.isExisting ? source.source_id : undefined,
        name: source.name,
        server_url: source.server_url,
        description: source.description || undefined,
        instructions: source.instructions || undefined,
        credentials: source.credentials && Object.keys(source.credentials).length > 0 
          ? source.credentials 
          : undefined
      }))

      const updateData = {
        name: formData.name,
        description: formData.description,
        is_public: formData.is_public,
        allowed_user_ids: formData.allowed_user_ids,
        sources: formattedSources
      }
      
      await api.updateBot(editingBot.bot_id, updateData)
      setShowEditForm(false)
      setEditingBot(null)
      resetForms()
      await loadBots()
    } catch (err) {
      setError('Failed to update bot: ' + err.message)
    }
  }

  const handleDeleteBot = async (botId) => {
    if (!confirm('Are you sure you want to delete this bot? This action cannot be undone.')) {
      return
    }
    
    try {
      await api.deleteBot(botId)
      await loadBots()
    } catch (err) {
      setError('Failed to delete bot: ' + err.message)
    }
  }

  const handleRemoveSource = (index) => {
    setFormData(prev => ({
      ...prev,
      sources: prev.sources.filter((_, i) => i !== index)
    }))
  }

  const handleEditSource = (index) => {
    const source = formData.sources[index]
    setCurrentSource({
      ...source,
      editIndex: index // Mark which source we're editing
    })
    setShowSourceForm(true)
  }

  const handleAddSource = () => {
    // Basic validation
    if (!currentSource.name) {
      setError('Please provide a source name')
      return
    }

    if (!currentSource.server_url) {
      setError('Please provide a server URL')
      return
    }

    // Simplified source handling - prepare credentials based on auth method
    let sourceToAdd = { ...currentSource }
    
    if (currentSource.auth_method === 'headers') {
      // Parse JSON headers
      try {
        const headers = JSON.parse(currentSource.auth_headers || '{}')
        sourceToAdd.credentials = { auth_headers: headers }
      } catch (err) {
        setError('Invalid JSON format in auth headers')
        return
      }
    } else {
      // URL-embedded: use the URL as-is, empty credentials
      sourceToAdd.credentials = {}
    }

    if (currentSource.editIndex !== undefined) {
      // Editing existing source
      const updatedSources = [...formData.sources]
      updatedSources[currentSource.editIndex] = {
        ...sourceToAdd,
        editIndex: undefined
      }
      setFormData(prev => ({
        ...prev,
        sources: updatedSources
      }))
    } else {
      // Adding new source
      setFormData(prev => ({
        ...prev,
        sources: [...prev.sources, sourceToAdd]
      }))
    }
    
    setCurrentSource({
      name: '',
      description: '',
      instructions: '',
      server_url: '',
      auth_method: 'headers',
      auth_headers: '',
      credentials: {}
    })
    setShowSourceForm(false)
  }

  const handleViewBot = async (botId) => {
    try {
      const botDetails = await api.getBot(botId)
      setSelectedBot(botDetails)
      setShowBotDetails(true)
    } catch (err) {
      setError('Failed to load bot details: ' + err.message)
    }
  }

  const handleEditBotClick = (bot) => {
    setEditingBot(bot)
    setFormData({
      name: bot.name,
      description: bot.description || '',
      sources: [], // We'll load the actual sources
      is_public: bot.is_public,
      allowed_user_ids: bot.allowed_user_ids || []
    })
    // Load the bot's current sources
    loadBotSources(bot.bot_id)
    setShowEditForm(true)
  }

  const loadBotSources = async (botId) => {
    try {
      const botDetails = await api.getBot(botId)
      // Convert bot sources to the format expected by the form
      const sourcesForForm = botDetails.sources.map(source => ({
        source_id: source.source_id, // Keep track of existing source ID
        name: source.name,
        description: source.description || '',
        instructions: source.instructions || '',
        server_url: source.server_url,
        auth_method: 'headers', // Default for existing sources
        auth_headers: '', // Don't show actual credentials
        credentials: {}, // Don't show actual credentials
        isExisting: true // Mark as existing source
      }))
      
      setFormData(prev => ({
        ...prev,
        sources: sourcesForForm
      }))
    } catch (err) {
      setError('Failed to load bot sources: ' + err.message)
    }
  }

  const getBotTypeIcon = (bot) => {
    if (bot.is_public) {
      return <Globe className="h-4 w-4 text-green-500" />
    } else {
      return <Lock className="h-4 w-4 text-blue-500" />
    }
  }

  const getBotTypeLabel = (bot) => {
    if (bot.is_public) {
      return 'Public Bot'
    } else {
      return `Private Bot (${bot.allowed_user_ids.length} users)`
    }
  }

  const handleRefreshSourceTools = async (sourceId, sourceName) => {
    try {
      setRefreshingSourceId(sourceId)
      const result = await api.refreshSourceTools(sourceId)
      
      // Backend returns RefreshResponse with: message, tools_count, timestamp
      // No 'success' field - if we get here without exception, it succeeded
      alert(`✅ Successfully refreshed tools for "${sourceName}"!\n\n${result.tools_count} tools loaded.`)
      
      // Reload bot data to get updated tool cache status
      await loadBots()
      
      // If bot details modal is open, refresh that data too
      if (showBotDetails && selectedBot) {
        try {
          const updatedBotDetails = await api.getBot(selectedBot.bot_id)
          setSelectedBot(updatedBotDetails)
        } catch (err) {
          console.error('Failed to refresh bot details:', err)
        }
      }
    } catch (err) {
      alert(`❌ Failed to refresh "${sourceName}": ${err.message}`)
    } finally {
      setRefreshingSourceId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader className="h-6 w-6 animate-spin text-scintilla-500" />
        <span className="ml-2 text-gray-600">Loading bots...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Available Bots
          </h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            Collections of sources configured by administrators
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>Create Bot</span>
          </button>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-red-700 dark:text-red-300 text-sm">{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Create Bot Form */}
      {showCreateForm && isAdmin && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Create New Bot
          </h3>
          <form onSubmit={handleCreateBot} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Bot Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                  placeholder="e.g., Development Team Bot"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Access Type
                </label>
                <select
                  value={formData.is_public ? 'public' : 'private'}
                  onChange={(e) => setFormData({...formData, is_public: e.target.value === 'public'})}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                >
                  <option value="public">Public (All Users)</option>
                  <option value="private">Private (Selected Users)</option>
                </select>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                rows={2}
                placeholder="Optional description of this bot's purpose"
              />
            </div>

            {/* Sources Section */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Bot Sources ({formData.sources.length} configured)
                </label>
                <button
                  type="button"
                  onClick={() => setShowSourceForm(true)}
                  className="text-sm bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-300 px-3 py-1 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-500 transition-colors"
                >
                  Add Source
                </button>
              </div>
              
              <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-lg p-3">
                {formData.sources.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No sources configured. Add sources for this bot to connect to.
                  </p>
                ) : (
                  formData.sources.map((source, index) => (
                    <div key={index} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                            {source.name}
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {source.server_url}
                          </p>
                          {source.description && (
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                              {source.description}
                            </p>
                          )}
                          {source.instructions && (
                            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                              Instructions: {source.instructions}
                            </p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveSource(index)}
                          className="text-red-500 hover:text-red-700 ml-2"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="flex items-center space-x-3 pt-4">
              <button
                type="submit"
                disabled={!formData.name.trim() || formData.sources.length === 0}
                className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create Bot
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false)
                  resetForms()
                }}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Add/Edit Source Form Modal */}
      {showSourceForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {currentSource.editIndex !== undefined ? 'Edit Source' : 'Add Source to Bot'}
                </h3>
                <button
                  onClick={() => {
                    setShowSourceForm(false)
                    setCurrentSource({
                      name: '',
                      description: '',
                      instructions: '',
                      server_url: '',
                      auth_method: 'headers',
                      auth_headers: '',
                      credentials: {}
                    })
                  }}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Source Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={currentSource.name}
                    onChange={(e) => setCurrentSource({...currentSource, name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                    placeholder="e.g., Jira Integration"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Authentication Method *
                  </label>
                  <select
                    required
                    value={currentSource.auth_method}
                    onChange={(e) => handleAuthMethodChange(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                  >
                    {Object.entries(AUTH_METHODS).map(([method, config]) => (
                      <option key={method} value={method}>
                        {config.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {AUTH_METHODS[currentSource.auth_method].description}
                  </p>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Server URL *
                  </label>
                  <input
                    type="url"
                    required
                    value={currentSource.server_url}
                    onChange={(e) => setCurrentSource({...currentSource, server_url: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                    placeholder={AUTH_METHODS[currentSource.auth_method].placeholder}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {currentSource.auth_method === 'url_embedded' 
                      ? 'Include authentication parameters directly in the URL'
                      : 'Base URL without authentication parameters'
                    }
                  </p>
                </div>

                {/* Header-based authentication field */}
                {currentSource.auth_method === 'headers' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Authentication Headers *
                    </label>
                    <textarea
                      required
                      value={currentSource.auth_headers}
                      onChange={(e) => setCurrentSource({...currentSource, auth_headers: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white font-mono text-sm"
                      rows={3}
                      placeholder={AUTH_METHODS.headers.placeholder}
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      JSON object with authentication headers
                    </p>
                  </div>
                )}
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </label>
                  <textarea
                    value={currentSource.description}
                    onChange={(e) => setCurrentSource({...currentSource, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                    rows={2}
                    placeholder="Optional description"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Instructions for Bot
                  </label>
                  <textarea
                    value={currentSource.instructions}
                    onChange={(e) => setCurrentSource({...currentSource, instructions: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                    rows={3}
                    placeholder="How should this source be used? What types of queries should it handle?"
                  />
                </div>
              </div>
              
              <div className="flex items-center space-x-3 mt-6">
                <button
                  onClick={handleAddSource}
                  className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
                >
                  {currentSource.editIndex !== undefined ? 'Update Source' : 'Add Source'}
                </button>
                <button
                  onClick={() => {
                    setShowSourceForm(false)
                    setCurrentSource({
                      name: '',
                      description: '',
                      instructions: '',
                      server_url: '',
                      auth_method: 'headers',
                      auth_headers: '',
                      credentials: {}
                    })
                  }}
                  className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Bot Form */}
      {showEditForm && editingBot && isAdmin && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Edit Bot: {editingBot.name}
          </h3>
          <form onSubmit={handleEditBot} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Bot Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Access Type
                </label>
                <select
                  value={formData.is_public ? 'public' : 'private'}
                  onChange={(e) => setFormData({...formData, is_public: e.target.value === 'public'})}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                >
                  <option value="public">Public (All Users)</option>
                  <option value="private">Private (Selected Users)</option>
                </select>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                rows={2}
              />
            </div>

            {/* Sources Section for Edit */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Bot Sources ({formData.sources.length} configured)
                </label>
                <button
                  type="button"
                  onClick={() => setShowSourceForm(true)}
                  className="text-sm bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-300 px-3 py-1 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-500 transition-colors"
                >
                  Add Source
                </button>
              </div>
              
              <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-lg p-3">
                {formData.sources.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No sources configured. Add sources for this bot to connect to.
                  </p>
                ) : (
                  formData.sources.map((source, index) => (
                    <div key={index} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                              {source.name}
                            </h4>
                            {source.isExisting && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-300">
                                Existing
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {source.server_url}
                          </p>
                          {source.description && (
                            <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                              {source.description}
                            </p>
                          )}
                          {source.instructions && (
                            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                              Instructions: {source.instructions}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center space-x-1 ml-2">
                          <button
                            type="button"
                            onClick={() => handleEditSource(index)}
                            className="text-blue-500 hover:text-blue-700"
                            title="Edit source"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveSource(index)}
                            className="text-red-500 hover:text-red-700"
                            title="Remove source"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="flex items-center space-x-3 pt-4">
              <button
                type="submit"
                className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
              >
                Update Bot
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowEditForm(false)
                  setEditingBot(null)
                  resetForms()
                }}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Bots Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {bots.map((bot) => (
          <div
            key={bot.bot_id}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-r from-scintilla-500 to-scintilla-600 rounded-full flex items-center justify-center">
                  <Bot className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {bot.name}
                  </h3>
                  <div className="flex items-center space-x-2 mt-1">
                    {getBotTypeIcon(bot)}
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {getBotTypeLabel(bot)}
                    </span>
                  </div>
                </div>
              </div>
              
              {isAdmin && (
                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => handleEditBotClick(bot)}
                    className="p-2 text-gray-400 hover:text-blue-500 transition-colors"
                    title="Edit bot"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteBot(bot.bot_id)}
                    className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                    title="Delete bot"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleViewBot(bot.bot_id)}
                    className="p-2 text-gray-400 hover:text-scintilla-500 transition-colors"
                    title="View details"
                  >
                    <Eye className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>

            {bot.description && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                {bot.description}
              </p>
            )}

            {/* Bot Sources */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Sources ({(botSources[bot.bot_id] || []).length})
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Created {new Date(bot.created_at).toLocaleDateString()}
                </span>
              </div>
              
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {(botSources[bot.bot_id] || []).length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                    No sources configured
                  </p>
                ) : (
                  (botSources[bot.bot_id] || []).map((source) => (
                    <div key={source.source_id} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                            {source.name}
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {source.server_url}
                          </p>
                          {source.instructions && (
                            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1 truncate" title={source.instructions}>
                              Instructions: {source.instructions}
                            </p>
                          )}
                        </div>
                        <button
                          onClick={() => handleRefreshSourceTools(source.source_id, source.name)}
                          disabled={refreshingSourceId === source.source_id}
                          className="flex items-center space-x-1 px-2 py-1 text-xs bg-scintilla-50 dark:bg-scintilla-900/20 text-scintilla-600 dark:text-scintilla-400 rounded hover:bg-scintilla-100 dark:hover:bg-scintilla-900/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ml-2"
                          title={`Refresh tools for ${source.name}`}
                        >
                          <RefreshCw className={`h-3 w-3 ${refreshingSourceId === source.source_id ? 'animate-spin' : ''}`} />
                          <span className="hidden sm:inline">
                            {refreshingSourceId === source.source_id ? 'Refreshing...' : 'Refresh'}
                          </span>
                        </button>
                      </div>

                      {/* Tool Information Section */}
                      <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center space-x-2">
                            <span className={`flex items-center space-x-1 text-xs ${getToolStatusColor(source.tools_cache_status)}`}>
                              {getToolStatusIcon(source.tools_cache_status)}
                              <span className="capitalize">
                                {source.tools_cache_status || 'Unknown'} Tools
                              </span>
                            </span>
                            {source.cached_tool_count > 0 && (
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                ({source.cached_tool_count} tools)
                              </span>
                            )}
                          </div>
                          
                          {/* Tools toggle button */}
                          {source.cached_tools && source.cached_tools.length > 0 && (
                            <button
                              onClick={() => toggleToolsExpansion(source.source_id)}
                              className="flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                            >
                              {expandedTools[source.source_id] ? (
                                <ChevronDown className="h-3 w-3" />
                              ) : (
                                <ChevronRight className="h-3 w-3" />
                              )}
                              <span>Tools</span>
                            </button>
                          )}
                        </div>

                        {/* Tool cache timestamp */}
                        {source.tools_last_cached_at && (
                          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                            Last cached: {new Date(source.tools_last_cached_at).toLocaleString()}
                          </div>
                        )}

                        {/* Tool cache error */}
                        {source.tools_cache_error && (
                          <div className="text-xs text-red-600 dark:text-red-400 mb-1 p-1 bg-red-50 dark:bg-red-900/20 rounded">
                            Error: {source.tools_cache_error}
                          </div>
                        )}

                        {/* Expanded tools list */}
                        {expandedTools[source.source_id] && source.cached_tools && source.cached_tools.length > 0 && (
                          <div className="mt-1 p-2 bg-white dark:bg-gray-800 rounded text-xs">
                            <div className="font-medium text-gray-700 dark:text-gray-300 mb-1">Available Tools:</div>
                            <div className="grid grid-cols-1 gap-1 max-h-20 overflow-y-auto">
                              {source.cached_tools.map((toolName, index) => (
                                <div key={index} className="font-mono text-gray-600 dark:text-gray-400 truncate">
                                  • {toolName}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* No tools message */}
                        {source.tools_cache_status === 'cached' && (!source.cached_tools || source.cached_tools.length === 0) && (
                          <div className="text-xs text-yellow-600 dark:text-yellow-400">
                            No tools available from this source
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Action Buttons */}
            {!isAdmin && (
              <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <button
                  onClick={() => handleViewBot(bot.bot_id)}
                  className="flex items-center space-x-1 px-3 py-1.5 text-xs bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors w-full justify-center"
                >
                  <Eye className="h-3 w-3" />
                  <span>View Details</span>
                </button>
              </div>
            )}


          </div>
        ))}
      </div>

      {bots.length === 0 && !showCreateForm && (
        <div className="text-center py-12">
          <Bot className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            No bots available
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-2">
            {isAdmin 
              ? "Create your first bot to get started" 
              : "Contact your administrator to set up bots for your team"
            }
          </p>
          {isAdmin && (
            <button
              onClick={() => setShowCreateForm(true)}
              className="mt-4 px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
            >
              Create Your First Bot
            </button>
          )}
        </div>
      )}

      {/* Bot Details Modal */}
      {showBotDetails && selectedBot && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 bg-gradient-to-r from-scintilla-500 to-scintilla-600 rounded-full flex items-center justify-center">
                    <Bot className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white">
                      {selectedBot.name}
                    </h3>
                    <div className="flex items-center space-x-2 mt-1">
                      {getBotTypeIcon(selectedBot)}
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        {getBotTypeLabel(selectedBot)}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setShowBotDetails(false)}
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {selectedBot.description && (
                <div className="mb-6">
                  <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </h4>
                  <p className="text-gray-600 dark:text-gray-400">
                    {selectedBot.description}
                  </p>
                </div>
              )}

              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Sources ({selectedBot.sources?.length || 0})
                </h4>
                <div className="space-y-3">
                  {selectedBot.sources?.map((source) => (
                    <div
                      key={source.source_id}
                      className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-2">
                            <h5 className="font-medium text-gray-900 dark:text-white">
                              {source.name}
                            </h5>
                            <button
                              onClick={() => handleRefreshSourceTools(source.source_id, source.name)}
                              disabled={refreshingSourceId === source.source_id}
                              className="flex items-center space-x-1 px-2 py-1 text-xs bg-scintilla-50 dark:bg-scintilla-900/20 text-scintilla-600 dark:text-scintilla-400 rounded hover:bg-scintilla-100 dark:hover:bg-scintilla-900/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              title={`Refresh tools for ${source.name}`}
                            >
                              <RefreshCw className={`h-3 w-3 ${refreshingSourceId === source.source_id ? 'animate-spin' : ''}`} />
                              <span>
                                {refreshingSourceId === source.source_id ? 'Refreshing...' : 'Refresh'}
                              </span>
                            </button>
                          </div>
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            {source.server_url}
                          </p>
                          {source.description && (
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                              {source.description}
                            </p>
                          )}
                          {source.instructions && (
                            <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                              <p className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-1">
                                Instructions:
                              </p>
                              <p className="text-sm text-blue-700 dark:text-blue-400">
                                {source.instructions}
                              </p>
                            </div>
                          )}

                          {/* Tool Information Section */}
                          <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-600">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center space-x-2">
                                <span className={`flex items-center space-x-1 text-sm ${getToolStatusColor(source.tools_cache_status)}`}>
                                  {getToolStatusIcon(source.tools_cache_status)}
                                  <span className="capitalize">
                                    {source.tools_cache_status || 'Unknown'} Tools
                                  </span>
                                </span>
                                {source.cached_tool_count > 0 && (
                                  <span className="text-sm text-gray-500 dark:text-gray-400">
                                    ({source.cached_tool_count} tools)
                                  </span>
                                )}
                              </div>
                              
                              {/* Tools toggle button */}
                              {source.cached_tools && source.cached_tools.length > 0 && (
                                <button
                                  onClick={() => toggleToolsExpansion(source.source_id)}
                                  className="flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                                >
                                  {expandedTools[source.source_id] ? (
                                    <ChevronDown className="h-3 w-3" />
                                  ) : (
                                    <ChevronRight className="h-3 w-3" />
                                  )}
                                  <span>Tools</span>
                                </button>
                              )}
                            </div>

                            {/* Tool cache timestamp */}
                            {source.tools_last_cached_at && (
                              <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                                Last cached: {new Date(source.tools_last_cached_at).toLocaleString()}
                              </div>
                            )}

                            {/* Tool cache error */}
                            {source.tools_cache_error && (
                              <div className="text-xs text-red-600 dark:text-red-400 mb-2 p-2 bg-red-50 dark:bg-red-900/20 rounded">
                                Error: {source.tools_cache_error}
                              </div>
                            )}

                            {/* Expanded tools list */}
                            {expandedTools[source.source_id] && source.cached_tools && source.cached_tools.length > 0 && (
                              <div className="mt-2 p-3 bg-white dark:bg-gray-800 rounded text-sm">
                                <div className="font-medium text-gray-700 dark:text-gray-300 mb-2">Available Tools:</div>
                                <div className="grid grid-cols-1 gap-1 max-h-32 overflow-y-auto">
                                  {source.cached_tools.map((toolName, index) => (
                                    <div key={index} className="font-mono text-gray-600 dark:text-gray-400">
                                      • {toolName}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* No tools message */}
                            {source.tools_cache_status === 'cached' && (!source.cached_tools || source.cached_tools.length === 0) && (
                              <div className="text-xs text-yellow-600 dark:text-yellow-400">
                                No tools available from this source
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )) || (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      No sources configured for this bot.
                    </p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Estimated Tools:</span>
                  <span className="ml-2 text-gray-900 dark:text-white font-medium">
                    {selectedBot.tool_count || 'Unknown'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Access:</span>
                  <span className="ml-2 text-gray-900 dark:text-white font-medium">
                    {selectedBot.user_has_access ? 'Granted' : 'Denied'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Created:</span>
                  <span className="ml-2 text-gray-700 dark:text-gray-300">
                    {new Date(selectedBot.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Updated:</span>
                  <span className="ml-2 text-gray-700 dark:text-gray-300">
                    {selectedBot.updated_at 
                      ? new Date(selectedBot.updated_at).toLocaleDateString()
                      : 'Never'
                    }
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
} 