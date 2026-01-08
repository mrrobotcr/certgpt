/**
 * ExamsGPT Server - Express + Socket.IO
 * Receives webhook from Python service and broadcasts to Vue frontend via WebSocket
 */

import express from 'express'
import { createServer } from 'http'
import { Server } from 'socket.io'
import cors from 'cors'
import path from 'path'
import { fileURLToPath } from 'url'

import webhookRouter from './routes/webhook.js'
import { Broadcaster } from './socket/broadcaster.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const PORT = process.env.PORT || 3000
const isDev = process.env.NODE_ENV !== 'production'

// Create Express app
const app = express()
const httpServer = createServer(app)

// Create Socket.IO server
const io = new Server(httpServer, {
  cors: isDev ? {
    origin: ['http://localhost:5173', 'http://127.0.0.1:5173'],
    methods: ['GET', 'POST']
  } : undefined,
  // Socket.IO will fall back to polling if WebSocket fails
  transports: ['websocket', 'polling']
})

// Create broadcaster singleton
const broadcaster = new Broadcaster(io)
app.locals.broadcaster = broadcaster

// Middleware
app.use(cors())
app.use(express.json())

// API Routes
app.use('/api', webhookRouter)

// Health check
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    connectedClients: io.sockets.sockets.size,
    timestamp: new Date().toISOString()
  })
})

// Serve static files in production
if (!isDev) {
  const staticPath = path.join(__dirname, '../../frontend/dist')
  app.use(express.static(staticPath))

  // SPA fallback - serve index.html for non-API routes
  app.get('*', (req, res) => {
    if (!req.path.startsWith('/api') && !req.path.startsWith('/socket.io')) {
      res.sendFile(path.join(staticPath, 'index.html'))
    }
  })
}

// Socket.IO connection handling
io.on('connection', (socket) => {
  console.log(`[Socket.IO] Client connected: ${socket.id}`)

  // Send current state to newly connected client
  broadcaster.sendCurrentState(socket)

  socket.on('disconnect', (reason) => {
    console.log(`[Socket.IO] Client disconnected: ${socket.id} (${reason})`)
  })

  socket.on('error', (error) => {
    console.error(`[Socket.IO] Socket error for ${socket.id}:`, error)
  })
})

// Start server
httpServer.listen(PORT, () => {
  console.log(`
╔══════════════════════════════════════════════════════════╗
║                  ExamsGPT Server                         ║
╠══════════════════════════════════════════════════════════╣
║  HTTP Server:    http://localhost:${PORT}                    ║
║  Socket.IO:      ws://localhost:${PORT}                      ║
║  Webhook:        POST /api/webhook                       ║
║  Health:         GET /api/health                         ║
║  Mode:           ${isDev ? 'Development' : 'Production'}                            ║
╚══════════════════════════════════════════════════════════╝
  `)
})

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('[Server] SIGTERM received, shutting down...')
  io.close()
  httpServer.close(() => {
    console.log('[Server] Closed')
    process.exit(0)
  })
})
