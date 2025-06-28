// Scintilla API Service
// Handles communication with the backend search system

// API URL detection now handled lazily in APIService.getBaseURL()

class APIService {
  constructor() {
    this.authToken = null
    
    // Calculate baseURL lazily to ensure window.location is available
    this.baseURL = this.getBaseURL()
    console.log('APIService initialized with baseURL:', this.baseURL)
    
    // Initialize with stored token if available
    const storedToken = localStorage.getItem('scintilla_token')
    if (storedToken) {
      this.authToken = storedToken
    }
  }

  getBaseURL() {
    // Smart API URL detection with lazy evaluation
    const viteApiUrl = import.meta.env.VITE_API_URL
    const isDev = import.meta.env.DEV
    
    if (viteApiUrl) {
      console.log('Using VITE_API_URL:', viteApiUrl)
      return viteApiUrl
    }
    
    if (isDev) {
      console.log('Development mode: using localhost')
      return 'http://localhost:8000'
    }
    
    // Production mode - ensure HTTPS if page is served over HTTPS
    if (typeof window !== 'undefined' && window.location.protocol === 'https:') {
      const httpsUrl = `https://${window.location.hostname}`
      console.log('Production HTTPS mode:', httpsUrl)
      return httpsUrl
    }
    
    // Fallback to relative URLs
    console.log('Using relative URLs')
    return ''
  }

  setAuthToken(token) {
    this.authToken = token
  }

  clearAuthToken() {
    this.authToken = null
  }

  getAuthHeaders() {
    const headers = {
      'Content-Type': 'application/json'
    }
    
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`
    }
    
    return headers
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`
    
    const config = {
      headers: {
        ...this.getAuthHeaders(),
        ...options.headers
      },
      ...options
    }

    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body)
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        const errorData = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorData}`)
      }

      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json()
      }
      
      return await response.text()
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error)
      throw error
    }
  }

  // Query endpoints - streaming
  async *query(data) {
    const url = `${this.baseURL}/api/query`
    
    const config = {
      method: 'POST',
      headers: {
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data)
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        const errorData = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorData}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          
          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })

          // Process complete lines
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // Keep incomplete line in buffer

          for (const line of lines) {
            const trimmedLine = line.trim()
            if (!trimmedLine) continue

            if (trimmedLine.startsWith('data: ')) {
              const jsonStr = trimmedLine.slice(6) // Remove "data: " prefix
              
              if (jsonStr === '[DONE]') {
                return
              }

              try {
                const chunk = JSON.parse(jsonStr)
                yield chunk
              } catch (parseError) {
                console.error('Failed to parse streaming chunk:', jsonStr, parseError)
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
          } catch (error) {
        console.error('Streaming query failed:', error)
        throw error
      }
  }

  // Sources endpoints
  async getSources() {
    return this.request('/api/sources')
  }

  async createSource(sourceData) {
    return this.request('/api/sources', {
      method: 'POST',
      body: sourceData
    })
  }

  async getSource(sourceId) {
    return this.request(`/api/sources/${sourceId}`)
  }

  async updateSource(sourceId, sourceData) {
    return this.request(`/api/sources/${sourceId}`, {
      method: 'PUT',
      body: sourceData
    })
  }

  async deleteSource(sourceId, force = false) {
    const url = `/api/sources/${sourceId}${force ? '?force=true' : ''}`
    return this.request(url, {
      method: 'DELETE'
    })
  }



  async refreshSourceTools(sourceId) {
    return this.request(`/api/sources/${sourceId}/refresh`, {
      method: 'POST'
    })
  }

  // Bots endpoints
  async getBots() {
    return this.request('/api/bots')
  }

  async createBot(botData) {
    return this.request('/api/bots', {
      method: 'POST',
      body: botData
    })
  }

  async getBot(botId) {
    return this.request(`/api/bots/${botId}`)
  }

  async updateBot(botId, botData) {
    return this.request(`/api/bots/${botId}`, {
      method: 'PUT',
      body: botData
    })
  }

  async deleteBot(botId) {
    return this.request(`/api/bots/${botId}`, {
      method: 'DELETE'
    })
  }

  async getAvailableSources() {
    return this.request('/api/bots/available-sources')
  }

  async getUsers() {
    return this.request('/api/users')
  }

  // Conversations endpoints
  async getConversations() {
    return this.request('/api/conversations')
  }

  async getConversation(conversationId) {
    return this.request(`/api/conversations/${conversationId}`)
  }

  async createConversation(data) {
    return this.request('/api/conversations', {
      method: 'POST',
      body: data
    })
  }

  async deleteConversation(conversationId) {
    return this.request(`/api/conversations/${conversationId}`, {
      method: 'DELETE'
    })
  }

  // Auth endpoints
  async getAuthConfig() {
    return this.request('/api/auth/config')
  }

  async login(googleToken) {
    return this.request('/api/auth/login', {
      method: 'POST',
      body: { google_token: googleToken }
    })
  }

  async getMe() {
    return this.request('/api/auth/me')
  }

  async logout() {
    return this.request('/api/auth/logout', {
      method: 'POST'
    })
  }

  // Agent Token endpoints
  async getAgentTokens() {
    return this.request('/api/agent-tokens/')
  }

  async createAgentToken(tokenData) {
    return this.request('/api/agent-tokens/', {
      method: 'POST',
      body: tokenData
    })
  }

  async deleteAgentToken(tokenId) {
    return this.request(`/api/agent-tokens/${tokenId}`, {
      method: 'DELETE'
    })
  }

  async deleteAllAgentTokens() {
    return this.request('/api/agent-tokens/', {
      method: 'DELETE'
    })
  }

  // Health check
  async healthCheck() {
    return this.request('/health')
  }
}

const api = new APIService()
export default api 