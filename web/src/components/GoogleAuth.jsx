import { useState, useEffect } from 'react'
import { User, LogOut, AlertCircle } from 'lucide-react'

const GoogleAuth = ({ onAuthChange }) => {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [authConfig, setAuthConfig] = useState(null)

  // Load Google OAuth script
  useEffect(() => {
    // Load auth config from backend
    fetch('/api/auth/config')
      .then(res => res.json())
      .then(config => {
        setAuthConfig(config)
        
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
      })
      .catch(err => {
        console.error('Failed to load auth config:', err)
        setError('Failed to load authentication configuration')
      })

    // Check for existing token
    const token = localStorage.getItem('scintilla_token')
    if (token) {
      validateToken(token)
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
      const response = await fetch('/api/auth/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const userData = await response.json()
        setUser(userData)
        onAuthChange?.(userData, token)
      } else {
        // Token invalid, remove it
        localStorage.removeItem('scintilla_token')
        setUser(null)
        onAuthChange?.(null, null)
      }
    } catch (err) {
      console.error('Token validation failed:', err)
      localStorage.removeItem('scintilla_token')
      setUser(null)
      onAuthChange?.(null, null)
    }
  }

  const handleGoogleLogin = async (response) => {
    setIsLoading(true)
    setError(null)

    try {
      const loginResponse = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          google_token: response.credential
        })
      })

      if (!loginResponse.ok) {
        const errorData = await loginResponse.json()
        throw new Error(errorData.detail || 'Login failed')
      }

      const data = await loginResponse.json()
      
      // Store token
      localStorage.setItem('scintilla_token', data.token)
      
      // Update user state
      setUser(data.user)
      onAuthChange?.(data.user, data.token)
      
    } catch (err) {
      console.error('Login failed:', err)
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
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('scintilla_token')}`
        }
      })
    } catch (err) {
      console.error('Logout request failed:', err)
    }

    // Clear local state regardless of API call success
    localStorage.removeItem('scintilla_token')
    setUser(null)
    onAuthChange?.(null, null)
    
    // Sign out from Google
    if (window.google?.accounts?.id) {
      window.google.accounts.id.disableAutoSelect()
    }
  }

  // Don't render if auth is not enabled
  if (authConfig && !authConfig.auth_enabled) {
    return (
      <div className="flex items-center space-x-2 text-gray-500">
        <User className="h-5 w-5" />
        <span className="text-sm">Dev Mode</span>
      </div>
    )
  }

  // Loading state
  if (!authConfig) {
    return (
      <div className="flex items-center space-x-2 text-gray-400">
        <User className="h-5 w-5 animate-pulse" />
        <span className="text-sm">Loading...</span>
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