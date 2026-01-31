/**
 * Socket.IO Broadcaster - Replaces SSE event emitter
 * Handles broadcasting events to all connected Socket.IO clients
 */

import { Server, Socket } from 'socket.io'

export interface AnswerData {
  type: 'answer'
  answer: string
  timestamp: string
  model?: string
  messageId?: string
}

export interface ProcessingData {
  type: 'processing'
  timestamp: string
  messageId?: string
  streaming?: boolean
}

export interface StreamingChunkData {
  type: 'streaming_chunk'
  content: string
  content_type: 'reasoning' | 'answer' | 'error'
  timestamp: string
  messageId?: string
}

export interface StreamingCompleteData {
  type: 'streaming_complete'
  answer: string
  timestamp: string
  model?: string
  elapsed_seconds?: number
  tokens_used?: number
  messageId?: string
  success: boolean
  error?: string
}

export interface QueueStatusData {
  type: 'queue_status'
  queue_size: number
  timestamp: string
}

export type EventData = AnswerData | ProcessingData | StreamingChunkData | StreamingCompleteData | QueueStatusData

function generateMessageId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
}

export class Broadcaster {
  private io: Server
  private latestAnswer: AnswerData | null = null
  private isProcessing: boolean = false
  private currentMessageId: string | null = null  // Renamed for clarity

  constructor(io: Server) {
    this.io = io
  }

  /**
   * Emit processing status to all connected clients
   */
  emitProcessing(data: Omit<ProcessingData, 'messageId'>): void {
    const messageId = generateMessageId()
    this.isProcessing = true
    this.currentMessageId = messageId

    const payload: ProcessingData = { ...data, messageId }
    this.io.emit('processing', payload)

    console.log(`[Broadcaster] Processing emitted [${messageId}]. Connected clients: ${this.io.sockets.sockets.size}`)
  }

  /**
   * Emit answer to all connected clients
   */
  emitAnswer(data: Omit<AnswerData, 'messageId'>): void {
    const messageId = generateMessageId()
    const payload: AnswerData = { ...data, messageId }

    this.latestAnswer = payload
    this.isProcessing = false
    this.currentMessageId = null

    this.io.emit('answer', payload)

    console.log(`[Broadcaster] Answer emitted [${messageId}]: ${data.answer.substring(0, 50)}... Connected clients: ${this.io.sockets.sockets.size}`)
  }

  /**
   * Emit streaming chunk to all connected clients
   */
  emitStreamingChunk(data: StreamingChunkData): void {
    // Use current message ID - must be set by emitProcessing first
    const messageId = data.messageId || this.currentMessageId || generateMessageId()

    // Update current message ID if this is a new streaming session
    if (!this.currentMessageId && data.messageId) {
      this.currentMessageId = data.messageId
    }

    const payload: StreamingChunkData = {
      ...data,
      messageId
    }

    this.io.emit('streaming_chunk', payload)

    const contentPreview = data.content.length > 30 ? data.content.substring(0, 30) + '...' : data.content
    console.log(`[Broadcaster] Streaming chunk emitted [${messageId}]: ${data.content_type} - ${contentPreview}`)
  }

  /**
   * Emit streaming completion to all connected clients
   */
  emitStreamingComplete(data: StreamingCompleteData): void {
    const messageId = data.messageId || this.currentMessageId || generateMessageId()
    const payload: StreamingCompleteData = { ...data, messageId }

    if (data.success && data.answer) {
      this.latestAnswer = {
        type: 'answer',
        answer: data.answer,
        timestamp: data.timestamp,
        model: data.model,
        messageId: messageId
      }
    }

    this.isProcessing = false
    this.currentMessageId = null  // Reset for next request

    this.io.emit('streaming_complete', payload)

    console.log(`[Broadcaster] Streaming complete emitted [${messageId}]: ${data.success ? 'Success' : 'Error'}`)
  }

  /**
   * Emit queue status to all connected clients
   */
  emitQueueStatus(data: QueueStatusData): void {
    this.io.emit('queue_status', data)
    console.log(`[Broadcaster] Queue status emitted: ${data.queue_size} screenshot(s)`)
  }

  /**
   * Send current state to a newly connected client
   */
  sendCurrentState(socket: Socket): void {
    // If currently processing, let client know
    if (this.isProcessing) {
      socket.emit('processing', {
        type: 'processing',
        timestamp: new Date().toISOString(),
        messageId: this.currentMessageId
      })
      console.log(`[Broadcaster] Sent processing state to ${socket.id}`)
    }

    // Send latest answer if exists
    if (this.latestAnswer) {
      socket.emit('answer', this.latestAnswer)
      console.log(`[Broadcaster] Sent latest answer to ${socket.id}`)
    }
  }

  /**
   * Get current state (for API endpoints)
   */
  getState() {
    return {
      isProcessing: this.isProcessing,
      currentMessageId: this.currentMessageId,
      latestAnswer: this.latestAnswer
    }
  }
}
