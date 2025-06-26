import { useState, useEffect } from 'react'
import { User, LogOut, AlertCircle } from 'lucide-react'
import api from '../services/api'

const GoogleAuth = ({ onAuthChange, showOnlyLogin = false }) => {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true) // Start as loading
  const [error, setError] = useState(null)
  const [authConfig, setAuthConfig] = useState(null)

  // Load Google OAuth script
  useEffect(() => {
    const loadAuthConfig = async () => {
      try {
        const config = await api.getAuthConfig()
        setAuthConfig(config)
        setIsLoading(false)
        
        if (config.auth_enabled && config.google_oauth_client_id) {
          // Load Google OAuth script
          const script = document.createElement('script')
          script.src = 'https://accounts.google.com/gsi/client'
          script.async = true
          script.defer = true
          document.body.appendChild(script)

          script.onload = () => {
            if (window.google) {
              initializeGoogleAuth(config.google_oauth_client_id)
            }
          }
        }
      } catch (err) {
        console.warn('Auth config load failed:', err.message)
        setError('Authentication system unavailable')
        setIsLoading(false)
      }
    }

    // Check for existing token first
    const token = localStorage.getItem('scintilla_token')
    if (token) {
      validateToken(token).finally(() => {
        if (!user) {
          loadAuthConfig()
        }
      })
    } else {
      loadAuthConfig()
    }
  }, [])

  const initializeGoogleAuth = (clientId) => {
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogleLogin,
      auto_select: false,
      cancel_on_tap_outside: true
    })
  }

  const validateToken = async (token) => {
    try {
      // Set token in API service temporarily for validation
      const oldToken = api.authToken
      api.setAuthToken(token)
      
      const userData = await api.getMe()
      setUser(userData)
      setIsLoading(false)
      onAuthChange?.(userData, token)
      return true
    } catch (err) {
      console.warn('Token validation failed:', err.message)
      localStorage.removeItem('scintilla_token')
      setUser(null)
      setIsLoading(false)
      onAuthChange?.(null, null)
      api.clearAuthToken()
      return false
    }
  }

  const handleGoogleLogin = async (response) => {
    setIsLoading(true)
    setError(null)

    try {
      const data = await api.login(response.credential)
      
      // Store token
      localStorage.setItem('scintilla_token', data.token)
      
      // Set token in API service for subsequent requests
      api.setAuthToken(data.token)
      
      // Update user state
      setUser(data.user)
      onAuthChange?.(data.user, data.token)
      
      // Validate token immediately to ensure state synchronization
      await validateToken(data.token)
      
    } catch (err) {
      console.warn('Login failed:', err.message)
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleLogin = () => {
    if (window.google && authConfig?.google_oauth_client_id) {
      window.google.accounts.id.prompt()
    } else {
      setError('Google OAuth not available')
    }
  }

  const handleLogout = async () => {
    try {
      // Call logout endpoint
      await api.logout()
    } catch (err) {
      console.error('Logout request failed:', err)
    }

    // Clear local state regardless of API call success
    localStorage.removeItem('scintilla_token')
    api.clearAuthToken()
    setUser(null)
    onAuthChange?.(null, null)
    
    // Sign out from Google
    if (window.google?.accounts?.id) {
      window.google.accounts.id.disableAutoSelect()
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-gray-400">
        <User className="h-5 w-5 animate-pulse" />
        <span className="text-sm">Loading...</span>
      </div>
    )
  }

  // Don't render if auth is not enabled (dev mode) - auto-authenticate
  if (authConfig && !authConfig.auth_enabled) {
    // In dev mode, auto-authenticate as a mock user
    if (!user) {
      const mockUser = {
        name: 'Developer',
        email: 'dev@ignitetech.com',
        picture_url: null
      }
      setUser(mockUser)
      onAuthChange?.(mockUser, 'dev-token')
    }
    
    return (
      <div className="flex items-center space-x-2 text-gray-500">
        <User className="h-5 w-5" />
        <span className="text-sm">Dev Mode</span>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center space-x-2 text-red-500">
        <AlertCircle className="h-5 w-5" />
        <span className="text-sm">{error}</span>
        <button 
          onClick={() => setError(null)}
          className="text-xs underline hover:no-underline"
        >
          Retry
        </button>
      </div>
    )
  }

  // Authenticated state
  if (user) {
    return (
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          {user.picture_url ? (
            <img 
              src={user.picture_url} 
              alt={user.name} 
              className="h-8 w-8 rounded-full"
            />
          ) : (
            <div className="h-8 w-8 rounded-full bg-gray-300 flex items-center justify-center">
              <User className="h-4 w-4 text-gray-600" />
            </div>
          )}
          <div className="flex flex-col">
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {user.name}
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {user.email}
            </span>
          </div>
        </div>
        
        <button
          onClick={handleLogout}
          className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          title="Sign out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    )
  }

  // Unauthenticated state
  if (showOnlyLogin) {
    // Landing page style - large prominent button
    return (
      <div className="flex flex-col items-center space-y-4">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
            Welcome to Scintilla
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Please sign in with your IgniteTech account to continue
          </p>
        </div>
        <button
          onClick={handleLogin}
          disabled={isLoading}
          className={`flex items-center space-x-3 px-8 py-4 text-lg font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 ${
            isLoading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          <User className="h-6 w-6" />
          <span>{isLoading ? 'Signing in...' : 'Sign in with Google'}</span>
        </button>
        {error && (
          <div className="text-red-600 text-sm mt-2 max-w-md text-center">
            {error}
          </div>
        )}
      </div>
    )
  }

  // Header style - compact button
  return (
    <div className="flex items-center space-x-2">
      <button
        onClick={handleLogin}
        disabled={isLoading}
        className={`flex items-center space-x-2 px-3 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors ${
          isLoading ? 'opacity-50 cursor-not-allowed' : ''
        }`}
      >
        <User className="h-4 w-4" />
        <span>{isLoading ? 'Signing in...' : 'Sign in with Google'}</span>
      </button>
    </div>
  )
}

export default GoogleAuth 