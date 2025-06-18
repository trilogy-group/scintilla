import { useState, useEffect } from 'react'
import { Bot, Users, Globe, Lock, Plus, Settings, Eye, Loader, AlertCircle } from 'lucide-react'
import api from '../services/api'

export const BotsManager = () => {
  const [bots, setBots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedBot, setSelectedBot] = useState(null)
  const [showBotDetails, setShowBotDetails] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [sources, setSources] = useState([])

  // Form state for creating bots
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    source_ids: [],
    is_public: false,
    allowed_user_ids: []
  })

  useEffect(() => {
    loadBots()
    checkAdminStatus()
    loadSources()
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

  const loadSources = async () => {
    try {
      const sourcesData = await api.getSources()
      setSources(sourcesData)
    } catch (err) {
      console.error('Failed to load sources:', err)
    }
  }

  const loadBots = async () => {
    try {
      setLoading(true)
      const botsData = await api.getBots()
      setBots(botsData)
      setError(null)
    } catch (err) {
      setError('Failed to load bots: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateBot = async (e) => {
    e.preventDefault()
    try {
      await api.createBot(formData)
      setShowCreateForm(false)
      setFormData({
        name: '',
        description: '',
        source_ids: [],
        is_public: false,
        allowed_user_ids: []
      })
      await loadBots()
    } catch (err) {
      setError('Failed to create bot: ' + err.message)
    }
  }

  const handleSourceToggle = (sourceId) => {
    setFormData(prev => ({
      ...prev,
      source_ids: prev.source_ids.includes(sourceId)
        ? prev.source_ids.filter(id => id !== sourceId)
        : [...prev.source_ids, sourceId]
    }))
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

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Select Sources ({formData.source_ids.length} selected)
              </label>
              <div className="max-h-48 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-lg p-3 space-y-2">
                {sources.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No sources available. Create sources first in the Sources tab.
                  </p>
                ) : (
                  sources.map((source) => (
                    <label key={source.source_id} className="flex items-center space-x-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.source_ids.includes(source.source_id)}
                        onChange={() => handleSourceToggle(source.source_id)}
                        className="rounded border-gray-300 text-scintilla-600 focus:ring-scintilla-500"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {source.name}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                          ({source.server_type})
                        </span>
                        {source.description && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            {source.description}
                          </p>
                        )}
                      </div>
                    </label>
                  ))
                )}
              </div>
            </div>

            <div className="flex items-center space-x-3 pt-4">
              <button
                type="submit"
                disabled={!formData.name.trim() || formData.source_ids.length === 0}
                className="px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create Bot
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
              <button
                onClick={() => handleViewBot(bot.bot_id)}
                className="p-2 text-gray-400 hover:text-scintilla-500 transition-colors"
                title="View details"
              >
                <Eye className="h-4 w-4" />
              </button>
            </div>

            {bot.description && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                {bot.description}
              </p>
            )}

            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-500 dark:text-gray-400">Sources:</span>
                <span className="text-gray-900 dark:text-white font-medium">
                  {bot.source_ids.length}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500 dark:text-gray-400">Created:</span>
                <span className="text-gray-700 dark:text-gray-300">
                  {new Date(bot.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={() => handleViewBot(bot.bot_id)}
                className="w-full px-4 py-2 text-sm bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
              >
                View Details
              </button>
            </div>
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
                  ✕
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
                        <div>
                          <h5 className="font-medium text-gray-900 dark:text-white">
                            {source.name}
                          </h5>
                          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            {source.server_type} • {source.server_url}
                          </p>
                          {source.description && (
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                              {source.description}
                            </p>
                          )}
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