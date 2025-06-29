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
  const [refreshingSourceId, setRefreshingSourceId] = useState(null)
  const [expandedTools, setExpandedTools] = useState({}) // Track which source tools are expanded
  
  // Available sources and users for sharing
  const [availableSources, setAvailableSources] = useState([])
  const [availableUsers, setAvailableUsers] = useState([])

  // Form state for creating/editing bots
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    sourceConfigs: [],  // New: array of {type: 'create'|'reference', data: {...}}
    is_public: false,
    shared_with_users: []
  })

  // Source form state
  const [currentSourceConfig, setCurrentSourceConfig] = useState({
    type: 'reference',  // Default to reference mode as requested
    data: {
      // For reference type
      source_id: null,
      custom_instructions: '',
      // For create type  
      name: '',
      description: '',
      instructions: '',
      server_url: '',
      auth_method: 'headers',
      auth_headers: '',
      credentials: {}
    }
  })

  // Authentication method configurations (simplified)
  const AUTH_METHODS = {
    headers: {
      label: 'Header-based Authentication',
      description: 'Use custom headers (Authorization, Bearer tokens, etc.)',
      placeholder: '{"Authorization": "Bearer your-token", "Custom-Header": "your-value"}'
    },
    url_embedded: {
      label: 'URL-embedded Authentication', 
      description: 'API key/credentials embedded in the URL',
      placeholder: 'https://server.com/sse?x-api-key=your-key&other=params'
    }
  }

  // Handle auth method change - reset credentials
  const handleAuthMethodChange = (newMethod) => {
    setCurrentSourceConfig(prev => ({
      ...prev,
      data: {
        ...prev.data,
        auth_method: newMethod,
        auth_headers: '',
        server_url: ''
      }
    }))
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
    loadAvailableResources()
  }, [])

  const loadAvailableResources = async () => {
    try {
      // Load available sources for bot configuration
      const sourcesData = await api.getAvailableSources()
      setAvailableSources(sourcesData)
      
      // Load available users for sharing
      const usersData = await api.getUsers()
      setAvailableUsers(usersData)
    } catch (err) {
      console.error('Failed to load available resources:', err)
      // Don't set error here as this is not critical
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
          sourcesData[bot.bot_id] = botDetails.source_associations || []
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
      sourceConfigs: [],
      is_public: false,
      shared_with_users: []
    })
    setCurrentSourceConfig({
      type: 'reference',
      data: {
        source_id: null,
        custom_instructions: '',
        name: '',
        description: '',
        instructions: '',
        server_url: '',
        auth_method: 'headers',
        auth_headers: '',
        credentials: {}
      }
    })
    setShowSourceForm(false)
  }

  const handleCreateBot = async (e) => {
    e.preventDefault()
    try {
      // Convert sourceConfigs to API format
      const botData = {
        name: formData.name,
        description: formData.description,
        source_configs: formData.sourceConfigs.map(config => ({
          type: config.type,
          create_data: config.type === 'create' ? {
            name: config.data.name,
            server_url: config.data.server_url,
            credentials: config.data.credentials,
            description: config.data.description,
            instructions: config.data.instructions
          } : null,
          reference_data: config.type === 'reference' ? {
            source_id: config.data.source_id,
            custom_instructions: config.data.custom_instructions
          } : null
        })),
        is_public: formData.is_public,
        shared_with_users: formData.shared_with_users
      }

      await api.createBot(botData)
      setShowCreateForm(false)
      resetForms()
      await loadBots()
    } catch (err) {
      setError('Failed to create bot: ' + err.message)
    }
  }

  const handleUpdateBot = async (e) => {
    e.preventDefault()
    try {
      // Convert sourceConfigs to API format
      const botData = {
        name: formData.name,
        description: formData.description,
        source_configs: formData.sourceConfigs.map(config => ({
          type: config.type,
          create_data: config.type === 'create' ? {
            name: config.data.name,
            server_url: config.data.server_url,
            credentials: config.data.credentials,
            description: config.data.description,
            instructions: config.data.instructions
          } : null,
          reference_data: config.type === 'reference' ? {
            source_id: config.data.source_id,
            custom_instructions: config.data.custom_instructions
          } : null
        })),
        is_public: formData.is_public,
        shared_with_users: formData.shared_with_users
      }

      await api.updateBot(editingBot.bot_id, botData)
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

  const handleRemoveSourceConfig = (index) => {
    setFormData(prev => ({
      ...prev,
      sourceConfigs: prev.sourceConfigs.filter((_, i) => i !== index)
    }))
  }

  const handleEditSourceConfig = (index) => {
    const config = formData.sourceConfigs[index]
    setCurrentSourceConfig({
      ...config,
      editIndex: index // Mark which config we're editing
    })
    setShowSourceForm(true)
  }

  const handleAddSourceConfig = () => {
    // Basic validation
    if (currentSourceConfig.type === 'reference') {
      if (!currentSourceConfig.data.source_id) {
        setError('Please select a source')
        return
      }
    } else {
      if (!currentSourceConfig.data.name || !currentSourceConfig.data.server_url) {
        setError('Please provide source name and server URL')
        return
      }
    }

    // Prepare source config based on type
    let configToAdd = { ...currentSourceConfig }
    
    if (currentSourceConfig.type === 'create') {
      // Prepare credentials based on auth method
      if (currentSourceConfig.data.auth_method === 'headers') {
        try {
          const headers = JSON.parse(currentSourceConfig.data.auth_headers || '{}')
          configToAdd.data.credentials = { auth_headers: headers }
        } catch (err) {
          setError('Invalid JSON format in auth headers')
          return
        }
      } else {
        configToAdd.data.credentials = {}
      }
    }

    if (currentSourceConfig.editIndex !== undefined) {
      // Editing existing config
      const updatedConfigs = [...formData.sourceConfigs]
      updatedConfigs[currentSourceConfig.editIndex] = {
        ...configToAdd,
        editIndex: undefined
      }
      setFormData(prev => ({
        ...prev,
        sourceConfigs: updatedConfigs
      }))
    } else {
      // Adding new config
      setFormData(prev => ({
        ...prev,
        sourceConfigs: [...prev.sourceConfigs, configToAdd]
      }))
    }
    
    // Reset form
    setCurrentSourceConfig({
      type: 'reference',
      data: {
        source_id: null,
        custom_instructions: '',
        name: '',
        description: '',
        instructions: '',
        server_url: '',
        auth_method: 'headers',
        auth_headers: '',
        credentials: {}
      }
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

  const handleEditBot = async (botId) => {
    try {
      const botDetails = await api.getBot(botId)
      
      // Convert bot details to form format
      setFormData({
        name: botDetails.name,
        description: botDetails.description || '',
        sourceConfigs: botDetails.source_associations?.map(assoc => {
          // ALL source associations should be treated as 'reference' type
          // since we don't have the full source data (server_url, credentials) needed for 'create' type
          return {
            type: 'reference',
            data: {
              source_id: assoc.source_id,
              custom_instructions: assoc.custom_instructions || ''
            }
          }
        }) || [],
        is_public: botDetails.is_public,
        shared_with_users: botDetails.shared_with_users || []
      })
      
      setEditingBot(botDetails)
      setShowEditForm(true)
    } catch (err) {
      setError('Failed to load bot for editing: ' + err.message)
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
      return `Private Bot (${bot.shared_with_users?.length || 0} users)`
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

  const handleUserToggle = (userId, checked) => {
    setFormData(prev => ({
      ...prev,
      shared_with_users: checked 
        ? [...prev.shared_with_users, userId]
        : prev.shared_with_users.filter(id => id !== userId)
    }))
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
            Create and manage collections of sources for specific purposes
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
        >
          <Plus className="h-4 w-4" />
          <span>Create Bot</span>
        </button>
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
      {showCreateForm && (
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

            {/* User Sharing Section */}
            {!formData.is_public && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Share with Users (optional)
                </label>
                <div className="max-h-40 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-lg p-3 space-y-2">
                  {availableUsers.map(user => (
                    <label key={user.user_id} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={formData.shared_with_users.includes(user.user_id)}
                        onChange={(e) => handleUserToggle(user.user_id, e.target.checked)}
                        className="text-scintilla-500 focus:ring-scintilla-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">
                        {user.name} ({user.email})
                      </span>
                    </label>
                  ))}
                  {availableUsers.length === 0 && (
                    <p className="text-gray-500 text-sm">No other users available</p>
                  )}
                </div>
              </div>
            )}

            {/* Sources Section */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Bot Sources ({formData.sourceConfigs.length} configured)
                </label>
                <button
                  type="button"
                  onClick={() => setShowSourceForm(true)}
                  className="text-sm px-3 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded-lg transition-colors"
                >
                  Add Source
                </button>
              </div>
              
              {/* Source Configuration List */}
              <div className="space-y-2">
                {formData.sourceConfigs.map((config, index) => (
                  <div key={index} className="border border-gray-200 dark:border-gray-600 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium text-gray-900 dark:text-white">
                          {config.data.name || 
                           (config.type === 'reference' 
                             ? availableSources.find(s => s.source_id === config.data.source_id)?.name || 'Unknown Source'
                             : 'Unnamed Source'
                           )}
                        </h4>
                        <p className="text-sm text-gray-500">
                          {config.type === 'reference' ? 'Existing Source' : 'Bot Source'} 
                          {config.data.custom_instructions && ' • Custom instructions provided'}
                        </p>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          type="button"
                          onClick={() => handleEditSourceConfig(index)}
                          className="text-gray-400 hover:text-blue-500"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRemoveSourceConfig(index)}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                {formData.sourceConfigs.length === 0 && (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                    <Bot className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No sources configured yet</p>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-3 pt-4">
              <button
                type="submit"
                className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
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

      {/* Edit Bot Form */}
      {showEditForm && editingBot && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Edit Bot: {editingBot.name}
          </h3>
          <form onSubmit={handleUpdateBot} className="space-y-4">
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

            {/* User Sharing Section */}
            {!formData.is_public && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Share with Users (optional)
                </label>
                <div className="max-h-40 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-lg p-3 space-y-2">
                  {availableUsers.map(user => (
                    <label key={user.user_id} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={formData.shared_with_users.includes(user.user_id)}
                        onChange={(e) => handleUserToggle(user.user_id, e.target.checked)}
                        className="text-scintilla-500 focus:ring-scintilla-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">
                        {user.name} ({user.email})
                      </span>
                    </label>
                  ))}
                  {availableUsers.length === 0 && (
                    <p className="text-gray-500 text-sm">No other users available</p>
                  )}
                </div>
              </div>
            )}

            {/* Sources Section */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Bot Sources ({formData.sourceConfigs.length} configured)
                </label>
                <button
                  type="button"
                  onClick={() => setShowSourceForm(true)}
                  className="text-sm px-3 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded-lg transition-colors"
                >
                  Add Source
                </button>
              </div>
              
              {/* Source Configuration List */}
              <div className="space-y-2">
                {formData.sourceConfigs.map((config, index) => (
                  <div key={index} className="border border-gray-200 dark:border-gray-600 rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium text-gray-900 dark:text-white">
                          {config.data.name || 
                           (config.type === 'reference' 
                             ? availableSources.find(s => s.source_id === config.data.source_id)?.name || 'Unknown Source'
                             : 'Unnamed Source'
                           )}
                        </h4>
                        <p className="text-sm text-gray-500">
                          {config.type === 'reference' ? 'Existing Source' : 'Bot Source'} 
                          {config.data.custom_instructions && ' • Custom instructions provided'}
                        </p>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          type="button"
                          onClick={() => handleEditSourceConfig(index)}
                          className="text-gray-400 hover:text-blue-500"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRemoveSourceConfig(index)}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                {formData.sourceConfigs.length === 0 && (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                    <Bot className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No sources configured yet</p>
                  </div>
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

      {/* Source Configuration Form Modal */}
      {showSourceForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {currentSourceConfig.editIndex !== undefined ? 'Edit Source' : 'Add Source'}
                </h3>
                <button
                  onClick={() => setShowSourceForm(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                {/* Source Type Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Source Type *
                  </label>
                  <select
                    value={currentSourceConfig.type}
                    onChange={(e) => setCurrentSourceConfig(prev => ({
                      ...prev,
                      type: e.target.value,
                      data: {
                        source_id: null,
                        custom_instructions: '',
                        name: '',
                        description: '',
                        instructions: '',
                        server_url: '',
                        auth_method: 'headers',
                        auth_headers: '',
                        credentials: {}
                      }
                    }))}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                  >
                    <option value="reference">Use Existing Source</option>
                    <option value="create">Create New Source</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    {currentSourceConfig.type === 'reference' 
                      ? 'Reference an existing source with optional custom instructions'
                      : 'Create a new source owned by this bot'
                    }
                  </p>
                </div>

                {/* Reference Type Configuration */}
                {currentSourceConfig.type === 'reference' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Select Source *
                      </label>
                      <select
                        value={currentSourceConfig.data.source_id || ''}
                        onChange={(e) => setCurrentSourceConfig(prev => ({
                          ...prev,
                          data: { ...prev.data, source_id: e.target.value }
                        }))}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        required
                      >
                        <option value="">Choose a source...</option>
                        {availableSources.map(source => (
                          <option key={source.source_id} value={source.source_id}>
                            {source.name} ({source.owner_type === 'user' 
                              ? (source.is_shared_with_user ? 'Shared with you' : 'Your source')
                              : 'Bot source'
                            })
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Custom Instructions (optional)
                      </label>
                      <textarea
                        value={currentSourceConfig.data.custom_instructions}
                        onChange={(e) => setCurrentSourceConfig(prev => ({
                          ...prev,
                          data: { ...prev.data, custom_instructions: e.target.value }
                        }))}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        rows={4}
                        placeholder="Custom instructions for this source in this bot (optional)

Example: 'When searching Gmail, focus only on customer support emails from the last 30 days. Prioritize urgent issues marked with [URGENT] in the subject line.'"
                      />
                    </div>
                  </>
                )}

                {/* Create Type Configuration */}
                {currentSourceConfig.type === 'create' && (
                  <>
                    {/* Similar to SourcesManager form but embedded */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Name *
                        </label>
                        <input
                          type="text"
                          required
                          value={currentSourceConfig.data.name}
                          onChange={(e) => setCurrentSourceConfig(prev => ({
                            ...prev,
                            data: { ...prev.data, name: e.target.value }
                          }))}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                          placeholder="e.g., My MCP Server"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Authentication Method *
                        </label>
                        <select
                          required
                          value={currentSourceConfig.data.auth_method}
                          onChange={(e) => handleAuthMethodChange(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        >
                          {Object.entries(AUTH_METHODS).map(([method, config]) => (
                            <option key={method} value={method}>
                              {config.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Server URL *
                      </label>
                      <input
                        type="url"
                        required
                        value={currentSourceConfig.data.server_url}
                        onChange={(e) => setCurrentSourceConfig(prev => ({
                          ...prev,
                          data: { ...prev.data, server_url: e.target.value }
                        }))}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        placeholder={currentSourceConfig.data.auth_method === 'url_embedded' 
                          ? 'https://mcp-server.example.com/sse?x-api-key=your-key'
                          : 'https://mcp-server.example.com/sse'
                        }
                      />
                    </div>

                    {/* Header-based authentication field */}
                    {currentSourceConfig.data.auth_method === 'headers' && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Authentication Headers *
                        </label>
                        <textarea
                          required
                          value={currentSourceConfig.data.auth_headers}
                          onChange={(e) => setCurrentSourceConfig(prev => ({
                            ...prev,
                            data: { ...prev.data, auth_headers: e.target.value }
                          }))}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white font-mono text-sm"
                          rows={3}
                          placeholder={AUTH_METHODS.headers.placeholder}
                        />
                      </div>
                    )}

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Description
                      </label>
                      <textarea
                        value={currentSourceConfig.data.description}
                        onChange={(e) => setCurrentSourceConfig(prev => ({
                          ...prev,
                          data: { ...prev.data, description: e.target.value }
                        }))}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        rows={2}
                        placeholder="Optional description of this source"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Custom Instructions (optional)
                      </label>
                      <textarea
                        value={currentSourceConfig.data.custom_instructions}
                        onChange={(e) => setCurrentSourceConfig(prev => ({
                          ...prev,
                          data: { ...prev.data, custom_instructions: e.target.value }
                        }))}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                        rows={4}
                        placeholder="Custom instructions for this source in this bot (optional)

Example: 'When searching Gmail, focus only on customer support emails from the last 30 days. Prioritize urgent issues marked with [URGENT] in the subject line.'"
                      />
                    </div>
                  </>
                )}

                <div className="flex items-center space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={handleAddSourceConfig}
                    className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
                  >
                    {currentSourceConfig.editIndex !== undefined ? 'Update Source' : 'Add Source'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowSourceForm(false)}
                    className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bots List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {bots.map((bot) => (
          <div
            key={bot.bot_id}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {bot.name}
                </h3>
                <div className="flex items-center space-x-2 mt-1">
                  {getBotTypeIcon(bot)}
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {getBotTypeLabel(bot)}
                  </span>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleViewBot(bot.bot_id)}
                  className="p-2 text-gray-400 hover:text-scintilla-500 transition-colors"
                  title="View details"
                >
                  <Eye className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleEditBot(bot.bot_id)}
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
              </div>
            </div>

            {bot.description && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                {bot.description}
              </p>
            )}

            <div className="text-sm text-gray-500 dark:text-gray-400">
              <div className="flex items-center justify-between">
                <span>Sources: {botSources[bot.bot_id]?.length || 0}</span>
                <span>Tools: {botSources[bot.bot_id]?.reduce((acc, source) => acc + (source.cached_tool_count || 0), 0) || 0}</span>
              </div>
            </div>
          </div>
        ))}

        {bots.length === 0 && (
          <div className="col-span-full text-center py-12">
            <Bot className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No bots available
            </h3>
            <p className="text-gray-500 dark:text-gray-400 mb-4">
              Create your first bot to organize sources for specific purposes.
            </p>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
            >
              Create Your First Bot
            </button>
          </div>
        )}
      </div>

      {/* Bot Details Modal */}
      {showBotDetails && selectedBot && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                    {selectedBot.name}
                  </h2>
                  <div className="flex items-center space-x-2 mt-1">
                    {getBotTypeIcon(selectedBot)}
                    <span className="text-sm text-gray-500">
                      {getBotTypeLabel(selectedBot)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setShowBotDetails(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>

              {selectedBot.description && (
                <div className="mb-6">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Description</h3>
                  <p className="text-gray-600 dark:text-gray-400">{selectedBot.description}</p>
                </div>
              )}

              {/* Source Associations */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
                  Sources ({selectedBot.source_associations?.length || 0})
                </h3>
                
                {selectedBot.source_associations?.length > 0 ? (
                  <div className="space-y-4">
                    {selectedBot.source_associations.map((assoc) => (
                      <div key={assoc.source_id} className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center space-x-2">
                              <h4 className="font-medium text-gray-900 dark:text-white">
                                {assoc.source_name}
                              </h4>
                              <span className={`text-xs px-2 py-1 rounded-full ${
                                assoc.source_type === 'owned' ? 'bg-green-100 text-green-700' :
                                assoc.source_type === 'shared' ? 'bg-blue-100 text-blue-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>
                                {assoc.source_type === 'owned' ? 'Your Source' :
                                 assoc.source_type === 'shared' ? 'Shared Source' :
                                 'Bot Source'}
                              </span>
                            </div>
                            
                            {assoc.custom_instructions && (
                              <div className="mt-2">
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                  <strong>Custom Instructions:</strong> {assoc.custom_instructions}
                                </p>
                              </div>
                            )}
                            
                            {/* Tool count and status */}
                            <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500 dark:text-gray-400">
                              <span>
                                <strong>Tools:</strong> {assoc.cached_tool_count || 0}
                              </span>
                              {assoc.tools_cache_status && (
                                <span className={`flex items-center space-x-1 ${
                                  assoc.tools_cache_status === 'cached' ? 'text-green-600 dark:text-green-400' :
                                  assoc.tools_cache_status === 'pending' ? 'text-yellow-600 dark:text-yellow-400' :
                                  assoc.tools_cache_status === 'error' ? 'text-red-600 dark:text-red-400' :
                                  'text-gray-500 dark:text-gray-400'
                                }`}>
                                  {assoc.tools_cache_status === 'cached' && <CheckCircle className="h-3 w-3" />}
                                  {assoc.tools_cache_status === 'pending' && <Clock className="h-3 w-3" />}
                                  {assoc.tools_cache_status === 'error' && <AlertTriangle className="h-3 w-3" />}
                                  <span className="capitalize">{assoc.tools_cache_status}</span>
                                </span>
                              )}
                              {assoc.tools_last_cached_at && (
                                <span>
                                  Last updated: {new Date(assoc.tools_last_cached_at).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                          </div>
                          
                          <button
                            onClick={() => handleRefreshSourceTools(assoc.source_id, assoc.source_name)}
                            disabled={refreshingSourceId === assoc.source_id}
                            className="p-2 text-gray-400 hover:text-blue-500 transition-colors disabled:opacity-50"
                            title="Refresh tools"
                          >
                            {refreshingSourceId === assoc.source_id ? (
                              <Loader className="h-4 w-4 animate-spin" />
                            ) : (
                              <RefreshCw className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                    <Settings className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No sources configured</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
} 