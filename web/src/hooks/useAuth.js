import { useState, useEffect } from 'react'
import api from '../services/api'

export const useAuth = () => {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const checkAuth = async () => {
      // First check if auth is enabled
      try {
        const config = await api.getAuthConfig()
        if (!config.auth_enabled) {
          // Dev mode - auto authenticate
          const mockUser = {
            name: 'Developer',
            email: 'dev@ignitetech.com',
            picture_url: null
          }
          setUser(mockUser)
          setIsAuthenticated(true)
          setIsLoading(false)
          return
        }
      } catch (err) {
        console.warn('Could not check auth config:', err.message)
      }

      // Check for existing token on mount
      const token = localStorage.getItem('scintilla_token')
      if (token) {
        validateToken(token)
      } else {
        setIsLoading(false)
      }
    }

    checkAuth()
  }, [])

  const validateToken = async (token) => {
    try {
      // Set token in API service for validation
      api.setAuthToken(token)
      
      const userData = await api.getMe()
      setUser(userData)
      setIsAuthenticated(true)
    } catch (err) {
      console.warn('Token validation failed:', err.message)
      localStorage.removeItem('scintilla_token')
      api.clearAuthToken()
      setUser(null)
      setIsAuthenticated(false)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAuthChange = (userData, token) => {
    if (userData && token) {
      setUser(userData)
      setIsAuthenticated(true)
    } else {
      setUser(null)
      setIsAuthenticated(false)
    }
    setIsLoading(false)
  }

  const requireAuth = (currentView) => {
    // If not authenticated and not on landing page, should redirect
    return !isAuthenticated && currentView !== 'landing'
  }

  const logout = () => {
    localStorage.removeItem('scintilla_token')
    api.clearAuthToken()
    setUser(null)
    setIsAuthenticated(false)
  }

  return {
    user,
    isLoading,
    isAuthenticated,
    handleAuthChange,
    requireAuth,
    logout
  }
} 