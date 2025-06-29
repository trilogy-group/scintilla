import { useState, useEffect, useCallback } from 'react'
import api from '../services/api'

export const useScintilla = () => {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const [error, setError] = useState(null)
  const [onConversationCreated, setOnConversationCreated] = useState(null)
  const [isSavingConversation, setIsSavingConversation] = useState(false)

  // Check backend connection on mount
  useEffect(() => {
    checkConnection()
  }, [])

  const checkConnection = async () => {
    try {
      await api.healthCheck()
      setIsConnected(true)
      setError(null)
    } catch (err) {
      setIsConnected(false)
      setError('Backend connection failed')
      console.error('Connection check failed:', err)
    }
  }

  const setConversationCreatedCallback = useCallback((callback) => {
    setOnConversationCreated(() => callback)
  }, [])

  const startNewConversation = useCallback(() => {
    setCurrentConversationId(null)
    setMessages([])
    setError(null)
  }, [])

  const loadConversation = useCallback(async (conversationId) => {
    try {
      setIsLoading(true)
      const conversation = await api.getConversation(conversationId)
      
      // Convert messages to the format expected by the UI
      const formattedMessages = conversation.messages.map(msg => ({
        id: msg.message_id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at),
        toolCalls: msg.tools_used || [],
        sources: msg.citations || [],
        selectedBots: msg.selected_bots || []  // Preserve bot information if stored
      }))
      
      setMessages(formattedMessages)
      setCurrentConversationId(conversationId)
      setError(null)
    } catch (err) {
      setError(`Failed to load conversation: ${err.message}`)
      console.error('Load conversation failed:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const sendMessage = useCallback(async (message, options = {}) => {
    if (!message.trim()) return
    
    // Prevent sending messages while conversation is being saved
    if (isSavingConversation) {
      console.log('⏳ Conversation being saved, waiting...')
      return
    }

    const userMessage = {
      id: `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'user',
      content: message,
      timestamp: new Date(),
      selectedBots: options.selectedBots || []  // Store bot information with the message
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setError(null)

    // Start timing the query
    const queryStartTime = Date.now()
    console.log('🕐 Query started:', new Date().toISOString())

    try {
      // Default to streaming mode
      const queryOptions = {
        message,
        mode: options.mode || 'conversational',
        stream: options.stream !== false,
        requireSources: options.requireSources || false,
        minSources: options.minSources || 2,
        searchDepth: options.searchDepth || 'thorough',
        conversation_id: currentConversationId, // Include current conversation ID
        ...options
      }

      console.log('🔍 Query options being sent:', {
        conversation_id: currentConversationId,
        message_length: message.length,
        has_conversation_id: !!currentConversationId
      })

      if (queryOptions.stream) {
        await handleStreamingResponse(message, queryOptions, queryStartTime)
      } else {
        await handleNonStreamingResponse(message, queryOptions, queryStartTime)
      }
    } catch (err) {
      const queryEndTime = Date.now()
      const totalTime = queryEndTime - queryStartTime
      console.log(`❌ Query failed after ${totalTime}ms:`, err.message)
      
      setError(`Query failed: ${err.message}`)
      console.error('Send message failed:', err)
      
      // Add error message to chat
      const errorMessage = {
        id: `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        role: 'assistant',
        content: `Sorry, I encountered an error: ${err.message}. Please try again.`,
        timestamp: new Date(),
        isError: true
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }, [currentConversationId, isSavingConversation])

  const handleStreamingResponse = async (originalMessage, options, queryStartTime) => {
    const assistantMessage = {
      id: `assistant-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      toolCalls: [],
      isStreaming: true
    }

    setMessages(prev => [...prev, assistantMessage])

    let firstResponseTime = null
    let toolsStartTime = null
    let toolsEndTime = null
    let firstContentTime = null
    let finalResponseTime = null

    try {
      const stream = await api.query(options)
      let fullContent = ''
      let toolCalls = []

      for await (const chunk of stream) {
        const chunkTime = Date.now()
        
        if (!firstResponseTime) {
          firstResponseTime = chunkTime
          const timeToFirstResponse = chunkTime - queryStartTime
          console.log(`🚀 First response chunk received after ${timeToFirstResponse}ms`)
        }

        if (chunk.type === 'thinking') {
          // Update with thinking indicator
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessage.id 
              ? { ...msg, content: `💭 ${chunk.content}`, isThinking: true }
              : msg
          ))
        } else if (chunk.type === 'tool_call') {
          if (!toolsStartTime) {
            toolsStartTime = chunkTime
            const timeToToolsStart = chunkTime - queryStartTime
            console.log(`🔧 Tools execution started after ${timeToToolsStart}ms`)
          }
          
          toolCalls.push({
            name: chunk.tool_name,
            timestamp: new Date()
          })
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessage.id 
              ? { 
                  ...msg, 
                  toolCalls, 
                  content: `🔧 Using tool: ${chunk.tool_name}${toolCalls.length > 1 ? ` (${toolCalls.length} tools used)` : ''}`,
                  isUsingTools: true
                }
              : msg
          ))
        } else if (chunk.type === 'tool_result') {
          if (toolsStartTime && !toolsEndTime) {
            toolsEndTime = chunkTime
            const toolsExecutionTime = toolsEndTime - toolsStartTime
            console.log(`⚡ Tools execution completed in ${toolsExecutionTime}ms`)
          }
          
          // Check for truncation info
          const truncationInfo = chunk.result?.truncation_info
          let statusText = `📚 Processing results from ${toolCalls.length} tool${toolCalls.length > 1 ? 's' : ''}...`
          
          if (truncationInfo?.truncated) {
            const tokensSaved = truncationInfo.original_tokens - truncationInfo.final_tokens
            statusText += ` (Content optimized: ${tokensSaved.toLocaleString()} tokens saved)`
          }
          
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessage.id 
              ? { 
                  ...msg, 
                  content: statusText,
                  isProcessing: true,
                  truncationInfo: truncationInfo
                }
              : msg
          ))
        } else if (chunk.type === 'content') {
          if (!firstContentTime) {
            firstContentTime = chunkTime
            const timeToFirstContent = chunkTime - queryStartTime
            console.log(`📝 First content chunk received after ${timeToFirstContent}ms`)
          }
          
          fullContent += chunk.content
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessage.id 
              ? { ...msg, content: fullContent, isThinking: false, isStreaming: true }
              : msg
          ))
        } else if (chunk.type === 'final_response') {
          finalResponseTime = chunkTime
          const timeToFinalResponse = chunkTime - queryStartTime
          console.log(`✅ Final response received after ${timeToFinalResponse}ms`)
          
          // Set saving flag when final response is received
          setIsSavingConversation(true)
          
          fullContent = chunk.content
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessage.id 
              ? { 
                  ...msg, 
                  content: fullContent, 
                  toolCalls,
                  isStreaming: false,
                  isThinking: false,
                  isUsingTools: false,  // Clear tool execution status
                  isProcessing: false,  // Clear processing status
                  isComplete: true,
                  processingStats: chunk.processing_stats,
                  sources: chunk.sources || []  // Make sure sources are included
                }
              : msg
          ))
        } else if (chunk.type === 'conversation_saved') {
          // Always update conversation ID when we receive a conversation_saved event
          if (chunk.conversation_id) {
            const newConversationId = chunk.conversation_id
            console.log(`💾 Conversation saved: ${newConversationId}`)
            setCurrentConversationId(newConversationId)
            
            // Notify parent component about new conversation (only if it's actually new)
            if (newConversationId !== currentConversationId && onConversationCreated) {
              onConversationCreated(newConversationId)
            }
          }
          
          // Clear saving flag when conversation is saved
          setIsSavingConversation(false)
        } else if (chunk.type === 'complete') {
          const completeTime = chunkTime
          const totalQueryTime = completeTime - queryStartTime
          
          // Log comprehensive timing summary
          console.log('📊 Query Timing Summary:')
          console.log(`  Total time: ${totalQueryTime}ms`)
          if (firstResponseTime) console.log(`  Time to first response: ${firstResponseTime - queryStartTime}ms`)
          if (toolsStartTime) console.log(`  Time to tools start: ${toolsStartTime - queryStartTime}ms`)
          if (toolsEndTime && toolsStartTime) console.log(`  Tools execution time: ${toolsEndTime - toolsStartTime}ms`)
          if (firstContentTime) console.log(`  Time to first content: ${firstContentTime - queryStartTime}ms`)
          if (finalResponseTime) console.log(`  Time to final response: ${finalResponseTime - queryStartTime}ms`)
          
          // Log backend timing if available
          if (chunk.timing) {
            console.log('🔧 Backend Timing Breakdown:')
            console.log(`  Total backend time: ${chunk.timing.total_time_ms}ms`)
            console.log(`  MCP load time: ${chunk.timing.mcp_load_time_ms}ms`)
            console.log(`  DB save time: ${chunk.timing.db_save_time_ms}ms`)
          }
          
          // Clear saving flag when stream completes - conversation is saved in background
          console.log('🔓 Stream completed, clearing conversation saving flag')
          setIsSavingConversation(false)
          
          // Handle conversation creation/update from legacy complete chunk (fallback)
          if (chunk.conversation_id && chunk.conversation_id !== currentConversationId) {
            const newConversationId = chunk.conversation_id
            setCurrentConversationId(newConversationId)
            
            // Notify parent component about new conversation
            if (onConversationCreated) {
              onConversationCreated(newConversationId)
            }
          }
          
          // Final cleanup to ensure all status indicators are cleared
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessage.id 
              ? { 
                  ...msg,
                  isStreaming: false,
                  isThinking: false,
                  isUsingTools: false,
                  isProcessing: false,
                  isComplete: true,
                  // Add timing info to the message for potential display
                  queryTiming: {
                    totalTime: totalQueryTime,
                    timeToFirstResponse: firstResponseTime ? firstResponseTime - queryStartTime : null,
                    toolsExecutionTime: toolsEndTime && toolsStartTime ? toolsEndTime - toolsStartTime : null,
                    timeToFirstContent: firstContentTime ? firstContentTime - queryStartTime : null,
                    backendTiming: chunk.timing || null
                  }
                }
              : msg
          ))
        } else if (chunk.type === 'error') {
          throw new Error(chunk.error)
        }
      }
    } catch (err) {
      const errorTime = Date.now()
      const timeToError = errorTime - queryStartTime
      console.log(`❌ Stream error after ${timeToError}ms:`, err.message)
      
      setMessages(prev => prev.map(msg => 
        msg.id === assistantMessage.id 
          ? { 
              ...msg, 
              content: `Error: ${err.message}`, 
              isError: true,
              isStreaming: false 
            }
          : msg
      ))
      throw err
    }
  }

  const handleNonStreamingResponse = async (originalMessage, options, queryStartTime) => {
    try {
      const response = await api.query(options)
      
      const assistantMessage = {
        id: `assistant-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        role: 'assistant',
        content: response.content || 'No response received',
        timestamp: new Date(),
        toolCalls: response.tools_used || [],
        messageId: response.message_id
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      throw err
    }
  }

  const clearMessages = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  const retryConnection = useCallback(() => {
    checkConnection()
  }, [])

  return {
    messages,
    isLoading,
    isConnected,
    error,
    currentConversationId,
    isSavingConversation,
    sendMessage,
    clearMessages,
    retryConnection,
    checkConnection,
    startNewConversation,
    loadConversation,
    setConversationCreatedCallback
  }
} 