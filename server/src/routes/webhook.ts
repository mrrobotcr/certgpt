/**
 * Webhook route - Receives POST from Python ExamsGPT service
 * POST /api/webhook
 */

import { Router, Request, Response } from 'express'
import { Broadcaster } from '../socket/broadcaster.js'

const router = Router()

// Extend Express Request to include broadcaster
declare global {
  namespace Express {
    interface Application {
      locals: {
        broadcaster: Broadcaster
      }
    }
  }
}

interface WebhookBody {
  type?: 'answer' | 'processing' | 'streaming_chunk' | 'streaming_complete' | 'queue_status'
  answer?: string
  timestamp?: string
  model?: string
  content?: string
  content_type?: 'reasoning' | 'answer' | 'error'
  message_id?: string
  elapsed_seconds?: number
  tokens_used?: number
  success?: boolean
  error?: string
  streaming?: boolean
  queue_size?: number
}

router.post('/webhook', (req: Request, res: Response) => {
  try {
    const body: WebhookBody = req.body
    const broadcaster = req.app.locals.broadcaster as Broadcaster

    console.log('[Webhook] Received data:', body)

    const eventType = body.type || 'answer'

    // Handle processing event
    if (eventType === 'processing') {
      broadcaster.emitProcessing({
        type: 'processing',
        timestamp: body.timestamp || new Date().toISOString(),
        streaming: body.streaming
      })

      res.json({
        success: true,
        message: 'Processing status broadcasted'
      })
      return
    }

    // Handle queue status event
    if (eventType === 'queue_status') {
      broadcaster.emitQueueStatus({
        type: 'queue_status',
        queue_size: body.queue_size ?? 0,
        timestamp: body.timestamp || new Date().toISOString()
      })

      res.json({
        success: true,
        message: 'Queue status broadcasted'
      })
      return
    }

    // Handle streaming chunk event
    if (eventType === 'streaming_chunk') {
      if (!body.content || !body.content_type) {
        res.json({
          success: false,
          error: 'Missing required fields: content, content_type'
        })
        return
      }

      broadcaster.emitStreamingChunk({
        type: 'streaming_chunk',
        content: body.content,
        content_type: body.content_type,
        timestamp: body.timestamp || new Date().toISOString(),
        messageId: body.message_id
      })

      res.json({
        success: true,
        message: 'Streaming chunk broadcasted'
      })
      return
    }

    // Handle streaming complete event
    if (eventType === 'streaming_complete') {
      if (body.success === false) {
        // Error case
        broadcaster.emitStreamingComplete({
          type: 'streaming_complete',
          answer: '',
          timestamp: body.timestamp || new Date().toISOString(),
          success: false,
          error: body.error || 'Unknown error',
          messageId: body.message_id
        })
      } else {
        // Success case
        if (!body.answer) {
          res.json({
            success: false,
            error: 'Missing required field: answer'
          })
          return
        }

        broadcaster.emitStreamingComplete({
          type: 'streaming_complete',
          answer: body.answer,
          timestamp: body.timestamp || new Date().toISOString(),
          model: body.model,
          elapsed_seconds: body.elapsed_seconds,
          tokens_used: body.tokens_used,
          success: true,
          messageId: body.message_id
        })
      }

      res.json({
        success: true,
        message: 'Streaming completion broadcasted'
      })
      return
    }

    // Handle answer event (non-streaming, legacy)
    if (!body.answer) {
      res.json({
        success: false,
        error: 'Missing required field: answer'
      })
      return
    }

    broadcaster.emitAnswer({
      type: 'answer',
      answer: body.answer,
      timestamp: body.timestamp || new Date().toISOString(),
      model: body.model
    })

    res.json({
      success: true,
      message: 'Answer received and broadcasted'
    })

  } catch (error) {
    console.error('[Webhook] Error processing request:', error)
    res.status(500).json({
      success: false,
      error: 'Internal server error'
    })
  }
})

// GET endpoint to check current state (useful for debugging)
router.get('/status', (req: Request, res: Response) => {
  const broadcaster = req.app.locals.broadcaster as Broadcaster
  const state = broadcaster.getState()

  res.json({
    success: true,
    isProcessing: state.isProcessing,
    currentMessageId: state.currentMessageId,
    hasAnswer: !!state.latestAnswer
  })
})

export default router
