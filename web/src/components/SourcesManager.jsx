import React, { useState, useEffect } from 'react'
import { 
  Plus, 
  Trash2, 
  Loader, 
  AlertCircle, 
  X, 
  CheckCircle,
  Clock,
  AlertTriangle,
  Wrench,
  ChevronDown,
  ChevronRight
} from 'lucide-react'
import { useScintilla } from '../hooks/useScintilla'
import api from '../services/api'

export const SourcesManager = () => {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)


  const [refreshingSource, setRefreshingSource] = useState(null)
  const [expandedTools, setExpandedTools] = useState({})

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    instructions: '',
    server_url: '',
    auth_method: 'headers', // 'headers' or 'url_embedded'
    auth_headers: '',
    credentials: {}
  })

  // Authentication method configurations
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

  // Handle auth method change
  const handleAuthMethodChange = (newMethod) => {
    setFormData({
      ...formData,
      auth_method: newMethod,
      auth_headers: '',
      server_url: ''
    })
  }

  useEffect(() => {
    loadSources()
  }, [])

  const loadSources = async () => {
    try {
      setLoading(true)
      const sourcesData = await api.getSources()
      setSources(sourcesData)
      setError(null)
    } catch (err) {
      setError('Failed to load sources: ' + err.message)
    } finally {
      setLoading(false)
    }
  }



  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      instructions: '',
      server_url: '',
      auth_method: 'headers',
      auth_headers: '',
      credentials: {}
    })
  }

  const handleCreateSource = async (e) => {
    e.preventDefault()
    try {
      let sourceData = {
        name: formData.name,
        description: formData.description,
        instructions: formData.instructions,
        server_url: formData.server_url,
        credentials: {}
      }

      // Handle authentication based on method
      if (formData.auth_method === 'headers') {
        // Parse JSON headers
        try {
          const headers = JSON.parse(formData.auth_headers || '{}')
          sourceData.credentials = { auth_headers: headers }
        } catch (err) {
          setError('Invalid JSON format in auth headers')
          return
        }
      } else {
        // URL-embedded: use the URL as-is, empty credentials
        sourceData.credentials = {}
      }

      await api.createSource(sourceData)
      setShowCreateForm(false)
      resetForm()
      await loadSources()
    } catch (err) {
      setError('Failed to create source: ' + err.message)
    }
  }

  const handleDeleteSource = async (sourceId, force = false) => {
    try {
      const result = await api.deleteSource(sourceId, force)
      
      // Check if result is a warning (has warning field)
      if (result.warning) {
        // Show detailed confirmation dialog
        const botsList = result.bots_using_source
          .map(bot => `• ${bot.bot_name}${bot.custom_instructions ? ' (with custom instructions)' : ''}`)
          .join('\n')
        
        const confirmMessage = `${result.message}\n\nBots using this source:\n${botsList}\n\nDo you want to continue? The source will be removed from these bots but the bots will remain.`
        
        if (confirm(confirmMessage)) {
          // User confirmed, delete with force=true
          await handleDeleteSource(sourceId, true)
        }
        return
      }
      
      // Success response
      await loadSources()
    } catch (err) {
      setError('Failed to delete source: ' + err.message)
    }
  }



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

  const handleRefreshSourceTools = async (sourceId) => {
    try {
      setRefreshingSource(sourceId)
      const result = await api.refreshSourceTools(sourceId)
      alert(`Tools refreshed! Found ${result.tools_count} tools.`)
      await loadSources()
    } catch (err) {
      alert('Failed to refresh tools: ' + err.message)
    } finally {
      setRefreshingSource(null)
    }
  }

  const getAuthDisplay = (source) => {
    // Try to determine auth method from URL and show appropriately
    const url = source.server_url
    if (url && (url.includes('x-api-key=') || url.includes('api_key=') || url.includes('token='))) {
      return 'URL-embedded'
    } else {
      return 'Header-based'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader className="h-6 w-6 animate-spin text-scintilla-500" />
        <span className="ml-2 text-gray-600">Loading sources...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Personal Sources
          </h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            Your individual MCP connections (separate from bot sources)
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
        >
          <Plus className="h-4 w-4" />
          <span>Add Source</span>
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-red-700 dark:text-red-300 text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* Create Source Form */}
      {showCreateForm && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Add New Source
          </h3>
          <form onSubmit={handleCreateSource} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
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
                  value={formData.auth_method}
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
                  {AUTH_METHODS[formData.auth_method].description}
                </p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Server URL *
              </label>
              <input
                type="url"
                required
                value={formData.server_url}
                onChange={(e) => setFormData({...formData, server_url: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                placeholder={formData.auth_method === 'url_embedded' 
                  ? 'https://mcp-server.example.com/sse?x-api-key=your-key'
                  : 'https://mcp-server.example.com/sse'
                }
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {formData.auth_method === 'url_embedded' 
                  ? 'Complete MCP server URL with authentication parameters (x-api-key, tokens, etc.) included as query parameters'
                  : 'MCP server base URL (e.g., https://mcp-server.example.com or https://mcp-server.example.com/sse) - authentication will be sent separately in headers'
                }
              </p>
            </div>

            {/* Header-based authentication field */}
            {formData.auth_method === 'headers' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Authentication Headers *
                </label>
                <textarea
                  required
                  value={formData.auth_headers}
                  onChange={(e) => setFormData({...formData, auth_headers: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white font-mono text-sm"
                  rows={3}
                  placeholder={AUTH_METHODS.headers.placeholder}
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  JSON object with authentication headers. Common examples: Authorization (Bearer/Basic), custom API headers, etc.
                </p>
              </div>
            )}
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                rows={2}
                placeholder="Optional description of this source"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Instructions
              </label>
              <textarea
                value={formData.instructions}
                onChange={(e) => setFormData({...formData, instructions: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                rows={2}
                placeholder="Optional instructions for this source"
              />
            </div>

            <div className="flex items-center space-x-3 pt-4">
              <button
                type="submit"
                className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
              >
                Create Source
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false)
                  resetForm()
                }}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Sources List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {sources.map((source) => (
          <div
            key={source.source_id}
            className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  {source.name}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {getAuthDisplay(source)}
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleRefreshSourceTools(source.source_id)}
                  disabled={refreshingSource === source.source_id}
                  className="p-2 text-gray-400 hover:text-blue-500 transition-colors disabled:opacity-50"
                  title="Refresh tools"
                >
                  {refreshingSource === source.source_id ? (
                    <Loader className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </button>

                <button
                  onClick={() => handleDeleteSource(source.source_id)}
                  className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                  title="Delete source"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-2 text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">URL:</span>
                <span className="ml-2 text-gray-900 dark:text-white font-mono text-xs break-all">
                  {source.server_url}
                </span>
              </div>
              {source.description && (
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Description:</span>
                  <span className="ml-2 text-gray-700 dark:text-gray-300">
                    {source.description}
                  </span>
                </div>
              )}
              {source.instructions && (
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Instructions:</span>
                  <span className="ml-2 text-blue-700 dark:text-blue-300">
                    {source.instructions}
                  </span>
                </div>
              )}
            </div>

            {/* Tool Cache Status */}
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className={`${getToolStatusColor(source.tools_cache_status)}`}>
                    {getToolStatusIcon(source.tools_cache_status)}
                  </span>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {source.cached_tool_count || 0} tools
                  </span>
                </div>

                {source.cached_tools && source.cached_tools.length > 0 && (
                  <button
                    onClick={() => toggleToolsExpansion(source.source_id)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    {expandedTools[source.source_id] ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>

              {/* Expanded Tools List */}
              {expandedTools[source.source_id] && source.cached_tools && (
                <div className="mt-2 space-y-1">
                  {source.cached_tools.slice(0, 10).map((tool, index) => (
                    <div key={index} className="text-xs text-gray-600 dark:text-gray-400 pl-6">
                      • {tool}
                    </div>
                  ))}
                  {source.cached_tools.length > 10 && (
                    <div className="text-xs text-gray-500 dark:text-gray-500 pl-6">
                      ... and {source.cached_tools.length - 10} more
                    </div>
                  )}
                </div>
              )}

              {source.tools_cache_error && (
                <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                  Error: {source.tools_cache_error}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {sources.length === 0 && (
        <div className="text-center py-12">
          <Wrench className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No sources found
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            Add your first MCP source to get started
          </p>
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
          >
            Add Source
          </button>
        </div>
      )}
    </div>
  )
} 