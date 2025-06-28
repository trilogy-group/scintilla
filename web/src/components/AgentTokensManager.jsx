import { useState, useEffect } from 'react'
import { Key, Copy, Trash2, Plus, Eye, EyeOff, Clock, AlertCircle, CheckCircle } from 'lucide-react'
import api from '../services/api'

export function AgentTokensManager() {
  const [tokens, setTokens] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newTokenName, setNewTokenName] = useState('')
  const [newTokenExpires, setNewTokenExpires] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createdToken, setCreatedToken] = useState(null)
  const [showCreatedToken, setShowCreatedToken] = useState(false)
  const [copiedToken, setCopiedToken] = useState(false)

  // Load tokens on component mount
  useEffect(() => {
    loadTokens()
  }, [])

  const loadTokens = async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await api.getAgentTokens()
      setTokens(response.tokens || [])
    } catch (err) {
      console.error('Failed to load tokens:', err)
      setError('Failed to load agent tokens')
    } finally {
      setIsLoading(false)
    }
  }

  const createToken = async (e) => {
    e.preventDefault()
    
    try {
      setIsCreating(true)
      setError(null)
      
      const payload = { name: newTokenName || null }
      if (newTokenExpires) {
        payload.expires_days = parseInt(newTokenExpires)
      }
      
      const newToken = await api.createAgentToken(payload)
      
      // Show the created token
      setCreatedToken(newToken)
      setShowCreatedToken(true)
      
      // Reset form
      setNewTokenName('')
      setNewTokenExpires('')
      setShowCreateForm(false)
      
      // Reload tokens list
      loadTokens()
      
    } catch (err) {
      console.error('Failed to create token:', err)
      setError('Failed to create token: ' + (err.message || 'Unknown error'))
    } finally {
      setIsCreating(false)
    }
  }

  const deleteToken = async (tokenId, tokenName) => {
    if (!confirm(`Are you sure you want to revoke the token "${tokenName || 'Unnamed'}"? This cannot be undone.`)) {
      return
    }
    
    try {
      await api.deleteAgentToken(tokenId)
      
      // Remove from local state
      setTokens(tokens.filter(t => t.token_id !== tokenId))
      
    } catch (err) {
      console.error('Failed to delete token:', err)
      setError('Failed to revoke token: ' + (err.message || 'Unknown error'))
    }
  }

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedToken(true)
      setTimeout(() => setCopiedToken(false), 2000)
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = text
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setCopiedToken(true)
      setTimeout(() => setCopiedToken(false), 2000)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleDateString()
  }

  const formatTimeAgo = (dateString) => {
    if (!dateString) return 'Never'
    const date = new Date(dateString)
    const now = new Date()
    const diffTime = Math.abs(now - date)
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    
    if (diffDays === 1) return 'Today'
    if (diffDays === 2) return 'Yesterday'
    if (diffDays <= 7) return `${diffDays} days ago`
    return formatDate(dateString)
  }

  const isExpired = (expiresAt) => {
    if (!expiresAt) return false
    return new Date(expiresAt) < new Date()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white flex items-center">
            <Key className="h-5 w-5 mr-2 text-scintilla-600" />
            Agent Tokens
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Create tokens for local agents to authenticate with Scintilla
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center px-3 py-2 bg-scintilla-600 text-white rounded-lg hover:bg-scintilla-700 transition-colors text-sm"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Token
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
            <span className="text-red-700 dark:text-red-300 text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* Created Token Display */}
      {createdToken && (
        <div className="bg-green-50 dark:bg-green-900/50 border border-green-200 dark:border-green-800 rounded-lg p-4">
          <div className="flex items-center mb-3">
            <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
            <span className="text-green-700 dark:text-green-300 font-medium">Token Created Successfully!</span>
          </div>
          <p className="text-green-600 dark:text-green-400 text-sm mb-3">
            Copy this token now - it won't be shown again.
          </p>
          <div className="flex items-center space-x-2">
            <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded border font-mono text-sm p-2">
              {showCreatedToken ? createdToken.token : '••••••••••••••••••••••••••••••••••••••••'}
            </div>
            <button
              onClick={() => setShowCreatedToken(!showCreatedToken)}
              className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              {showCreatedToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
            <button
              onClick={() => copyToClipboard(createdToken.token)}
              className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              <Copy className="h-4 w-4" />
            </button>
          </div>
          {copiedToken && (
            <p className="text-green-600 dark:text-green-400 text-sm mt-2">✓ Copied to clipboard!</p>
          )}
          <button
            onClick={() => setCreatedToken(null)}
            className="mt-3 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Create Token Form */}
      {showCreateForm && (
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <h4 className="font-medium text-gray-900 dark:text-white mb-4">Create New Agent Token</h4>
          <form onSubmit={createToken} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Token Name (Optional)
              </label>
              <input
                type="text"
                value={newTokenName}
                onChange={(e) => setNewTokenName(e.target.value)}
                placeholder="e.g., Production Agent, Local Development"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Expires In (Days)
              </label>
              <select
                value={newTokenExpires}
                onChange={(e) => setNewTokenExpires(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              >
                <option value="">Never expires</option>
                <option value="30">30 days</option>
                <option value="90">90 days</option>
                <option value="180">180 days</option>
                <option value="365">1 year</option>
              </select>
            </div>
            <div className="flex space-x-3">
              <button
                type="submit"
                disabled={isCreating}
                className="flex-1 bg-scintilla-600 text-white py-2 px-4 rounded-lg hover:bg-scintilla-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isCreating ? 'Creating...' : 'Create Token'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="flex-1 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300 py-2 px-4 rounded-lg hover:bg-gray-400 dark:hover:bg-gray-500 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tokens List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-8">
            <div className="animate-spin h-8 w-8 border-4 border-scintilla-600 border-t-transparent rounded-full mx-auto"></div>
            <p className="text-gray-500 dark:text-gray-400 mt-2">Loading tokens...</p>
          </div>
        ) : tokens.length === 0 ? (
          <div className="text-center py-8">
            <Key className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
            <p className="text-gray-500 dark:text-gray-400">No agent tokens created yet</p>
            <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">Create a token to authenticate local agents</p>
          </div>
        ) : (
          tokens.map((token) => (
            <div
              key={token.token_id}
              className={`bg-white dark:bg-gray-800 rounded-lg border p-4 ${
                isExpired(token.expires_at) ? 'border-red-200 dark:border-red-800' : 'border-gray-200 dark:border-gray-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-sm bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                      {token.token_prefix}•••
                    </span>
                    {token.name && (
                      <span className="font-medium text-gray-900 dark:text-white">
                        {token.name}
                      </span>
                    )}
                    {isExpired(token.expires_at) && (
                      <span className="bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 px-2 py-1 rounded text-xs">
                        Expired
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500 dark:text-gray-400">
                    <div className="flex items-center">
                      <Clock className="h-4 w-4 mr-1" />
                      Created {formatTimeAgo(token.created_at)}
                    </div>
                    {token.last_used_at && (
                      <div>
                        Last used {formatTimeAgo(token.last_used_at)}
                      </div>
                    )}
                    {token.expires_at && (
                      <div>
                        Expires {formatDate(token.expires_at)}
                      </div>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => deleteToken(token.token_id, token.name)}
                  className="p-2 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                  title="Revoke token"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Usage Instructions */}
      <div className="bg-blue-50 dark:bg-blue-900/50 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">How to use agent tokens:</h4>
        <ol className="text-blue-800 dark:text-blue-200 text-sm space-y-1">
          <li>1. Create a new token above</li>
          <li>2. Copy the token (it's only shown once)</li>
          <li>3. Add it to your local agent config: <code className="bg-blue-100 dark:bg-blue-800 px-1 rounded">agent_token: "scat_..."</code></li>
          <li>4. Start your local agent</li>
        </ol>
      </div>
    </div>
  )
} 