// Test connection utility for frontend-backend integration
import api from '../services/api'

export const testConnection = async () => {
  console.log('🔗 Testing Scintilla backend connection...')
  
  try {
    // Test health endpoint
    console.log('📡 Checking health endpoint...')
    const health = await api.healthCheck()
    console.log('✅ Health check passed:', health)
    
    // Test stats
    console.log('📊 Loading stats...')
    const stats = await api.getStats()
    console.log('✅ Stats loaded:', stats)
    
    // NOTE: Disabled automatic query test to avoid creating conversations
    // Test simple query (non-streaming) - DISABLED
    // console.log('🔍 Testing simple query...')
    // const response = await api.query({
    //   message: 'Hello, can you help me?',
    //   stream: false,
    //   mode: 'conversational'
    // })
    // console.log('✅ Simple query response:', response)
    
    console.log('🎉 Connection tests passed! (Query test disabled)')
    return { success: true, health, stats }
    
  } catch (error) {
    console.error('❌ Connection test failed:', error)
    return { success: false, error: error.message }
  }
}

// Auto-run test when in development - but without the query that creates conversations
if (import.meta.env.DEV) {
  // Run test after a short delay to ensure components are loaded
  setTimeout(() => {
    testConnection()
  }, 2000)
} 