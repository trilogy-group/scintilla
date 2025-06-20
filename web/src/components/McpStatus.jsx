import { useState, useEffect } from 'react'
import { Server, RefreshCw, Database, Clock, CheckCircle, AlertCircle } from 'lucide-react'
import api from '../services/api'

export default function McpStatus() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const loadStatus = async () => {
    try {
      const response = await api.request('/api/mcp/status')
      setStatus(response.status)
      setError(null)
    } catch (err) {
      setError('Failed to load MCP status')
      console.error('Failed to load MCP status:', err)
    } finally {
      setLoading(false)
    }
  }

  const triggerRefresh = async () => {
    setRefreshing(true)
    try {
      await api.request('/api/mcp/refresh', { method: 'POST' })
      // Wait a moment then reload status
      setTimeout(() => {
        loadStatus()
        setRefreshing(false)
      }, 1000)
    } catch (err) {
      setError('Failed to trigger refresh')
      console.error('Failed to trigger refresh:', err)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadStatus()
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center space-x-2">
          <Server className="h-5 w-5 text-gray-400 animate-pulse" />
          <span className="text-sm text-gray-600 dark:text-gray-400">Loading MCP status...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800 p-4">
        <div className="flex items-center space-x-2">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <span className="text-sm text-red-600 dark:text-red-400">{error}</span>
        </div>
      </div>
    )
  }

  const formatCacheAge = (ageSeconds) => {
    if (ageSeconds < 60) return `${ageSeconds}s`
    if (ageSeconds < 3600) return `${Math.floor(ageSeconds / 60)}m`
    return `${Math.floor(ageSeconds / 3600)}h`
  }

  const getCacheSourceColor = (source) => {
    switch (source) {
      case 'database': return 'text-green-600 dark:text-green-400'
      case 'background_refresh': return 'text-blue-600 dark:text-blue-400'
      case 'empty': return 'text-yellow-600 dark:text-yellow-400'
      case 'test_mode': return 'text-purple-600 dark:text-purple-400'
      default: return 'text-gray-600 dark:text-gray-400'
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Database className="h-5 w-5 text-gray-500" />
          <span className="font-medium text-gray-900 dark:text-white">MCP Tool Cache</span>
        </div>
        
        <button
          onClick={triggerRefresh}
          disabled={refreshing}
          className="flex items-center space-x-1 px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${refreshing ? 'animate-spin' : ''}`} />
          <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
        </button>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-gray-600 dark:text-gray-400">Status:</span>
          <div className="flex items-center space-x-1">
            {status.cache_loaded ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <AlertCircle className="h-4 w-4 text-red-500" />
            )}
            <span className={status.cache_loaded ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
              {status.cache_loaded ? 'Loaded' : 'Not Loaded'}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-600 dark:text-gray-400">Tools:</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {status.tool_count}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-600 dark:text-gray-400">Servers:</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {status.loaded_servers?.length || 0}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-600 dark:text-gray-400">Cache Source:</span>
          <span className={`font-medium ${getCacheSourceColor(status.cache_source)}`}>
            {status.cache_source}
          </span>
        </div>

        {status.cache_age_seconds && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600 dark:text-gray-400">Cache Age:</span>
            <div className="flex items-center space-x-1">
              <Clock className="h-3 w-3 text-gray-400" />
              <span className="text-gray-900 dark:text-white">
                {formatCacheAge(status.cache_age_seconds)}
              </span>
            </div>
          </div>
        )}

        {status.background_refresh && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600 dark:text-gray-400">Background Refresh:</span>
            <span className={`text-xs px-2 py-1 rounded-full ${
              status.background_refresh.running 
                ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
            }`}>
              {status.background_refresh.running ? 'Running' : 'Idle'}
            </span>
          </div>
        )}

        {status.test_mode && (
          <div className="mt-2 p-2 bg-purple-50 dark:bg-purple-900/20 rounded border border-purple-200 dark:border-purple-800">
            <span className="text-xs text-purple-600 dark:text-purple-400">
              🧪 Test Mode Active
            </span>
          </div>
        )}
      </div>
    </div>
  )
} 