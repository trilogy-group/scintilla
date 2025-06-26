// Scintilla API Service
// Handles communication with the backend search system

// Smart API URL detection:
// - Development: Use full localhost URL (frontend runs on different port)
// - Production: Use relative URLs (frontend and backend on same domain)
// - Override: VITE_API_URL environment variable takes precedence
const BASE_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? 'http://localhost:8000' : '')

class APIService {
  constructor() {
    this.baseURL = BASE_URL
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`
    
    const config = {
      headers: {
        'Content-Type': 'application/json',
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
        'Content-Type': 'application/json',
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

  async deleteSource(sourceId) {
    return this.request(`/api/sources/${sourceId}`, {
      method: 'DELETE'
    })
  }

  async testSourceConnection(sourceId) {
    return this.request(`/api/sources/${sourceId}/test`, {
      method: 'POST'
    })
  }

  async refreshCache() {
    return this.request('/api/sources/refresh-cache', {
      method: 'POST'
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

  // Health check
  async healthCheck() {
    return this.request('/health')
  }
}

const api = new APIService()
export default api 