import { useState, useEffect } from 'react'
import { Plus, Settings, Trash2, TestTube, CheckCircle, AlertCircle, Loader, RefreshCw } from 'lucide-react'
import api from '../services/api'

export const SourcesManager = () => {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [testingSource, setTestingSource] = useState(null)
  const [refreshingCache, setRefreshingCache] = useState(false)

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    server_type: 'CUSTOM_SSE',
    server_url: '',
    credentials: {
      api_key: ''
    }
  })

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

  const handleRefreshCache = async () => {
    try {
      setRefreshingCache(true)
      const result = await api.refreshToolCache()
      if (result.success) {
        alert(`Tool cache refreshed! ${result.entries_removed} cache entries cleared.`)
      } else {
        alert('Failed to refresh cache: ' + result.message)
      }
    } catch (err) {
      alert('Failed to refresh cache: ' + err.message)
    } finally {
      setRefreshingCache(false)
    }
  }

  const handleCreateSource = async (e) => {
    e.preventDefault()
    try {
      await api.createSource(formData)
      setShowCreateForm(false)
      setFormData({
        name: '',
        description: '',
        server_type: 'CUSTOM_SSE',
        server_url: '',
        credentials: {
          api_key: ''
        }
      })
      await loadSources()
    } catch (err) {
      setError('Failed to create source: ' + err.message)
    }
  }

  const handleDeleteSource = async (sourceId) => {
    if (!confirm('Are you sure you want to delete this source?')) return
    
    try {
      await api.deleteSource(sourceId)
      await loadSources()
    } catch (err) {
      setError('Failed to delete source: ' + err.message)
    }
  }

  const handleTestSource = async (sourceId) => {
    try {
      setTestingSource(sourceId)
      const result = await api.testSourceConnection(sourceId)
      if (result.success) {
        alert(`Connection test successful! Found ${result.tool_count} tools.`)
      } else {
        alert('Connection test failed: ' + result.message)
      }
    } catch (err) {
      alert('Connection test failed: ' + err.message)
    } finally {
      setTestingSource(null)
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
            My Sources
          </h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            Manage your individual MCP server connections
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={handleRefreshCache}
            disabled={refreshingCache}
            className="flex items-center space-x-2 px-3 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 border border-gray-300 dark:border-gray-600 rounded-lg transition-colors disabled:opacity-50"
            title="Refresh tool cache - this will force reload tools on next query"
          >
            <RefreshCw className={`h-4 w-4 ${refreshingCache ? 'animate-spin' : ''}`} />
            <span className="text-sm">Refresh Cache</span>
          </button>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>Add Source</span>
          </button>
        </div>
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
                  placeholder="e.g., My Hive Server"
                />
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
                  placeholder="https://your-hive-server.com"
                />
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
                placeholder="Optional description of this source"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Key *
              </label>
              <input
                type="password"
                required
                value={formData.credentials.api_key}
                onChange={(e) => setFormData({
                  ...formData, 
                  credentials: {...formData.credentials, api_key: e.target.value}
                })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-scintilla-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                placeholder="Your MCP server API key"
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
                onClick={() => setShowCreateForm(false)}
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
                  {source.server_type}
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleTestSource(source.source_id)}
                  disabled={testingSource === source.source_id}
                  className="p-2 text-gray-400 hover:text-scintilla-500 transition-colors disabled:opacity-50"
                  title="Test connection"
                >
                  {testingSource === source.source_id ? (
                    <Loader className="h-4 w-4 animate-spin" />
                  ) : (
                    <TestTube className="h-4 w-4" />
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
                <span className="ml-2 text-gray-900 dark:text-white font-mono text-xs">
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
              <div>
                <span className="text-gray-500 dark:text-gray-400">Created:</span>
                <span className="ml-2 text-gray-700 dark:text-gray-300">
                  {new Date(source.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-sm text-green-600 dark:text-green-400">
                  Active
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {sources.length === 0 && !showCreateForm && (
        <div className="text-center py-12">
          <Settings className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            No sources configured yet
          </p>
          <p className="text-gray-400 dark:text-gray-500 text-sm mt-2">
            Add your first MCP server connection to get started
          </p>
          <button
            onClick={() => setShowCreateForm(true)}
            className="mt-4 px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors"
          >
            Add Your First Source
          </button>
        </div>
      )}
    </div>
  )
} 