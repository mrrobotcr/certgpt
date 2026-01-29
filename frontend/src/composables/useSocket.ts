/**
 * Socket.IO composable for Vue 3
 * Handles connection to server and real-time event handling
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { io, Socket } from 'socket.io-client'
import type { AnswerData, ProcessingData, StreamingChunkData, StreamingCompleteData } from '../types/events'

const PROCESSING_TIMEOUT_MS = 120000 // 2 minutes

export function useSocket() {
  const connected = ref(false)
  const isProcessing = ref(false)
  const currentAnswer = ref<AnswerData | null>(null)

  // Streaming state
  const isStreaming = ref(false)
  const streamingContent = ref<string>('')
  const streamingReasoning = ref<string>('')
  const streamingError = ref<string>('')
  const currentMessageId = ref<string | null>(null)
  const isSearching = ref(false)  // Web search indicator

  let socket: Socket | null = null
  let processingTimeout: ReturnType<typeof setTimeout> | null = null
  let jsonValidationTimer: ReturnType<typeof setTimeout> | null = null
  let streamingBuffer = ''

  const clearProcessingTimeout = () => {
    if (processingTimeout) {
      clearTimeout(processingTimeout)
      processingTimeout = null
    }
  }

  const clearJsonValidationTimer = () => {
    if (jsonValidationTimer) {
      clearTimeout(jsonValidationTimer)
      jsonValidationTimer = null
    }
  }

  const clearStreamingState = (preserveError: boolean = false) => {
    /** Clear all streaming state and buffers
     * @param preserveError - If true, keep the error state for display
     */
    isStreaming.value = false
    streamingContent.value = ''
    streamingReasoning.value = ''
    streamingBuffer = ''
    isSearching.value = false  // Reset search state
    if (!preserveError) {
      streamingError.value = ''
    }
    currentMessageId.value = null
    clearJsonValidationTimer()
  }

  const validateAndParseJSON = (content: string): boolean => {
    /**
     * Check if buffered content is valid JSON
     * Returns true if JSON is complete and valid
     */
    try {
      const trimmed = content.trim()
      if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        JSON.parse(trimmed)
        return true
      }
      return false
    } catch {
      return false
    }
  }

  const connect = () => {
    // In development, connect to separate server; in production, same origin
    const serverUrl = import.meta.env.DEV ? 'http://localhost:3000' : ''

    socket = io(serverUrl, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: Infinity
    })

    socket.on('connect', () => {
      console.log('[Socket.IO] Connected:', socket?.id)
      connected.value = true
    })

    socket.on('disconnect', (reason) => {
      console.log('[Socket.IO] Disconnected:', reason)
      connected.value = false
      // Clear streaming state on disconnect to prevent memory leaks
      clearStreamingState()
    })

    socket.on('connect_error', (error) => {
      console.error('[Socket.IO] Connection error:', error.message)
      connected.value = false
    })

    socket.on('processing', (data: ProcessingData) => {
      console.log('[Socket.IO] Processing started:', data.messageId, 'streaming:', data.streaming)
      isProcessing.value = true

      // Track message ID for streaming
      if (data.messageId) {
        currentMessageId.value = data.messageId
      }

      // Clear existing timeout
      clearProcessingTimeout()

      // Set timeout for stuck processing state
      processingTimeout = setTimeout(() => {
        if (isProcessing.value || isStreaming.value) {
          console.warn('[Socket.IO] Processing timeout - resetting state')
          isProcessing.value = false
          clearStreamingState()  // Clear all streaming state on timeout
        }
      }, PROCESSING_TIMEOUT_MS)
    })

    // Streaming chunk handler
    socket.on('streaming_chunk', (data: StreamingChunkData) => {
      console.log('[Socket.IO] Streaming chunk received:', data.content_type, data.messageId)

      // Set streaming state
      isStreaming.value = true
      isProcessing.value = false
      clearProcessingTimeout()

      // Track message ID
      if (data.messageId) {
        currentMessageId.value = data.messageId
      }

      // Handle different content types
      if (data.content_type === 'reasoning') {
        streamingReasoning.value += data.content
      } else if (data.content_type === 'answer') {
        streamingContent.value += data.content
        streamingBuffer += data.content

        // Try to validate JSON as content arrives
        clearJsonValidationTimer()
        jsonValidationTimer = setTimeout(() => {
          if (validateAndParseJSON(streamingBuffer)) {
            console.log('[Socket.IO] Valid JSON detected in stream')
          }
        }, 100) // Debounce JSON validation
      } else if (data.content_type === 'error') {
        streamingError.value += data.content
      } else if (data.content_type === 'searching') {
        // Handle web search status
        if (data.content === 'searching') {
          isSearching.value = true
        } else if (data.content === 'done') {
          isSearching.value = false
        }
      }
    })

    // Streaming completion handler
    socket.on('streaming_complete', (data: StreamingCompleteData) => {
      console.log('[Socket.IO] Streaming complete:', data.success, data.messageId)

      if (data.success && data.answer) {
        // Update current answer with final result
        currentAnswer.value = {
          type: 'answer',
          answer: data.answer,
          timestamp: data.timestamp,
          model: data.model,
          messageId: data.messageId
        }
        clearStreamingState(false)  // Clear everything including errors
      } else {
        // Handle error - preserve error state for display
        streamingError.value = data.error || 'Unknown streaming error'
        clearStreamingState(true)  // Clear everything except error
      }
    })

    socket.on('answer', (data: AnswerData) => {
      console.log('[Socket.IO] Answer received:', data.messageId)
      currentAnswer.value = data
      isProcessing.value = false
      clearProcessingTimeout()
    })
  }

  const disconnect = () => {
    if (socket) {
      socket.disconnect()
      socket = null
    }
    clearProcessingTimeout()
    clearJsonValidationTimer()
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    isProcessing,
    currentAnswer,
    // Streaming state
    isStreaming,
    streamingContent,
    streamingReasoning,
    streamingError,
    isSearching
  }
}
