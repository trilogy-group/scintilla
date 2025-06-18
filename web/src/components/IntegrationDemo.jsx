import { useState } from 'react'
import { Play, CheckCircle, AlertCircle, Loader } from 'lucide-react'
import { testConnection } from '../utils/testConnection'

export const IntegrationDemo = () => {
  const [isRunning, setIsRunning] = useState(false)
  const [results, setResults] = useState(null)

  const runDemo = async () => {
    setIsRunning(true)
    setResults(null)
    
    try {
      const testResults = await testConnection()
      setResults(testResults)
    } catch (error) {
      setResults({ success: false, error: error.message })
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Integration Test
        </h3>
        <button
          onClick={runDemo}
          disabled={isRunning}
          className="flex items-center space-x-2 px-4 py-2 bg-scintilla-500 text-white rounded-lg hover:bg-scintilla-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isRunning ? (
            <Loader className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          <span>{isRunning ? 'Testing...' : 'Run Test'}</span>
        </button>
      </div>

      {results && (
        <div className="space-y-3">
          <div className={`flex items-center space-x-2 ${
            results.success ? 'text-green-600' : 'text-red-600'
          }`}>
            {results.success ? (
              <CheckCircle className="h-5 w-5" />
            ) : (
              <AlertCircle className="h-5 w-5" />
            )}
            <span className="font-medium">
              {results.success ? 'Integration Test Passed!' : 'Integration Test Failed'}
            </span>
          </div>

          {results.success ? (
            <div className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <div>✅ Backend health check: {results.health?.status}</div>
              <div>✅ Stats loaded: {results.stats?.toolsAvailable} tools, {results.stats?.sourcesConnected} sources, {results.stats?.botsAvailable} bots</div>
              <div>✅ Query response: {results.response?.content ? 'Received' : 'Pending'}</div>
            </div>
          ) : (
            <div className="text-sm text-red-600 dark:text-red-400">
              ❌ Error: {results.error}
            </div>
          )}
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          This test verifies that the frontend can successfully communicate with the Scintilla backend API.
        </p>
      </div>
    </div>
  )
} 