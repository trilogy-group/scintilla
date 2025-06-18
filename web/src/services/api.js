// Scintilla API Service
// Handles communication with the backend search system

const API_BASE_URL = 'http://localhost:8000'

class ScintillaAPI {
  constructor() {
    this.baseURL = API_BASE_URL
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer mock_token_12345' // TODO: Replace with real auth
    }
  }

  // ========== SOURCES API ==========
  
  async getSources() {
    try {
      const response = await fetch(`${this.baseURL}/api/sources`, {
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to get sources: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to get sources:', error)
      throw error
    }
  }

  async createSource(sourceData) {
    try {
      const response = await fetch(`${this.baseURL}/api/sources`, {
        method: 'POST',
        headers: this.defaultHeaders,
        body: JSON.stringify(sourceData)
      })
      if (!response.ok) throw new Error(`Failed to create source: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to create source:', error)
      throw error
    }
  }

  async updateSource(sourceId, sourceData) {
    try {
      const response = await fetch(`${this.baseURL}/api/sources/${sourceId}`, {
        method: 'PUT',
        headers: this.defaultHeaders,
        body: JSON.stringify(sourceData)
      })
      if (!response.ok) throw new Error(`Failed to update source: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to update source:', error)
      throw error
    }
  }

  async deleteSource(sourceId) {
    try {
      const response = await fetch(`${this.baseURL}/api/sources/${sourceId}`, {
        method: 'DELETE',
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to delete source: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to delete source:', error)
      throw error
    }
  }

  async testSourceConnection(sourceId) {
    try {
      const response = await fetch(`${this.baseURL}/api/sources/${sourceId}/test`, {
        method: 'POST',
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to test source: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to test source:', error)
      throw error
    }
  }

  async refreshToolCache() {
    try {
      const response = await fetch(`${this.baseURL}/api/sources/refresh-cache`, {
        method: 'POST',
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to refresh tool cache: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to refresh tool cache:', error)
      throw error
    }
  }

  // ========== BOTS API ==========
  
  async getBots() {
    try {
      const response = await fetch(`${this.baseURL}/api/bots`, {
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to get bots: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to get bots:', error)
      throw error
    }
  }

  async getBot(botId) {
    try {
      const response = await fetch(`${this.baseURL}/api/bots/${botId}`, {
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to get bot: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to get bot:', error)
      throw error
    }
  }

  async createBot(botData) {
    try {
      const response = await fetch(`${this.baseURL}/api/bots`, {
        method: 'POST',
        headers: this.defaultHeaders,
        body: JSON.stringify(botData)
      })
      if (!response.ok) throw new Error(`Failed to create bot: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to create bot:', error)
      throw error
    }
  }

  async healthCheck() {
    try {
      const response = await fetch(`${this.baseURL}/health`)
      return await response.json()
    } catch (error) {
      console.error('Health check failed:', error)
      throw error
    }
  }

  async query(params) {
    const {
      message,
      mode = 'conversational',
      stream = true,
      requireSources = false,
      minSources = 2,
      searchDepth = 'thorough',
      llmProvider = 'anthropic',
      llmModel = 'claude-sonnet-4-20250514',
      botIds = null, // Array of bot IDs to use
      useUserSources = true // Whether to include user's personal sources
    } = params

    const payload = {
      message,
      bot_ids: botIds || [], // Use provided bot IDs or empty array
      use_user_sources: useUserSources,
      mode,
      require_sources: requireSources,
      min_sources: minSources,
      search_depth: searchDepth,
      stream,
      llm_provider: llmProvider,
      llm_model: llmModel
    }

    try {
      const response = await fetch(`${this.baseURL}/api/query`, {
        method: 'POST',
        headers: this.defaultHeaders,
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`)
      }

      if (stream) {
        return this.handleStreamingResponse(response)
      } else {
        return await response.json()
      }
    } catch (error) {
      console.error('Query failed:', error)
      throw error
    }
  }

  async *handleStreamingResponse(response) {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim() === '') continue
          
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              yield data
            } catch (e) {
              console.warn('Failed to parse SSE data:', line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  }

  async getStats() {
    try {
      // First check health
      const healthResponse = await fetch(`${this.baseURL}/health`)
      const health = await healthResponse.json()
      
      if (health.status !== 'healthy') {
        return {
          toolsAvailable: 0,
          sourcesConnected: 0,
          botsAvailable: 0,
          searchMode: 'unknown',
          status: 'disconnected'
        }
      }

      // Get user's sources and bots
      let sourcesCount = 0
      let botsCount = 0
      let toolsCount = 0
      
      try {
        // Get user sources
        const sourcesResponse = await fetch(`${this.baseURL}/api/sources`, {
          headers: this.defaultHeaders
        })
        if (sourcesResponse.ok) {
          const sources = await sourcesResponse.json()
          sourcesCount = sources.length
          toolsCount += sources.length * 8 // Estimate 8 tools per source
        }
        
        // Get accessible bots
        const botsResponse = await fetch(`${this.baseURL}/api/bots`, {
          headers: this.defaultHeaders
        })
        if (botsResponse.ok) {
          const bots = await botsResponse.json()
          botsCount = bots.length
          // Add estimated tools from bots
          bots.forEach(bot => {
            toolsCount += bot.source_ids.length * 8 // Estimate 8 tools per source
          })
        }
        
      } catch (apiError) {
        console.warn('Failed to get detailed stats, using fallback:', apiError)
      }
      
      return {
        toolsAvailable: toolsCount || 25, // Fallback value
        sourcesConnected: sourcesCount || 0,
        botsAvailable: botsCount || 0,
        searchMode: 'thorough',
        status: 'connected'
      }
    } catch (error) {
      console.error('Failed to get stats:', error)
      return {
        toolsAvailable: 0,
        sourcesConnected: 0,
        botsAvailable: 0,
        searchMode: 'unknown',
        status: 'disconnected'
      }
    }
  }

  // ========== CONVERSATIONS API ==========
  
  async getConversations() {
    try {
      const response = await fetch(`${this.baseURL}/api/conversations`, {
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to get conversations: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to get conversations:', error)
      throw error
    }
  }

  async getConversation(conversationId) {
    try {
      const response = await fetch(`${this.baseURL}/api/conversations/${conversationId}`, {
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to get conversation: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to get conversation:', error)
      throw error
    }
  }

  async deleteConversation(conversationId) {
    try {
      const response = await fetch(`${this.baseURL}/api/conversations/${conversationId}`, {
        method: 'DELETE',
        headers: this.defaultHeaders
      })
      if (!response.ok) throw new Error(`Failed to delete conversation: ${response.status}`)
      return await response.json()
    } catch (error) {
      console.error('Failed to delete conversation:', error)
      throw error
    }
  }
}

// Create singleton instance
const api = new ScintillaAPI()

export default api 