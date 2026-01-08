/**
 * Socket.IO composable for Vue 3
 * Handles connection to server and real-time event handling
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { io, Socket } from 'socket.io-client'
import type { AnswerData, ProcessingData } from '../types/events'

const PROCESSING_TIMEOUT_MS = 120000 // 2 minutes

export function useSocket() {
  const connected = ref(false)
  const isProcessing = ref(false)
  const currentAnswer = ref<AnswerData | null>(null)

  let socket: Socket | null = null
  let processingTimeout: ReturnType<typeof setTimeout> | null = null

  const clearProcessingTimeout = () => {
    if (processingTimeout) {
      clearTimeout(processingTimeout)
      processingTimeout = null
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
    })

    socket.on('connect_error', (error) => {
      console.error('[Socket.IO] Connection error:', error.message)
      connected.value = false
    })

    socket.on('processing', (data: ProcessingData) => {
      console.log('[Socket.IO] Processing started:', data.messageId)
      isProcessing.value = true

      // Clear existing timeout
      clearProcessingTimeout()

      // Set timeout for stuck processing state
      processingTimeout = setTimeout(() => {
        if (isProcessing.value) {
          console.warn('[Socket.IO] Processing timeout - resetting state')
          isProcessing.value = false
        }
      }, PROCESSING_TIMEOUT_MS)
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
    currentAnswer
  }
}
