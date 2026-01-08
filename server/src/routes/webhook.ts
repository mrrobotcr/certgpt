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
  type?: 'answer' | 'processing'
  answer?: string
  timestamp?: string
  model?: string
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
        timestamp: body.timestamp || new Date().toISOString()
      })

      res.json({
        success: true,
        message: 'Processing status broadcasted'
      })
      return
    }

    // Handle answer event
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
    lastMessageId: state.lastMessageId,
    hasAnswer: !!state.latestAnswer
  })
})

export default router
