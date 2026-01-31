<template>
  <div class="app">
    <!-- Floating Header -->
    <header class="header">
      <div class="logo">
        <span class="logo-icon">⚡</span>
        <span class="logo-text">ExamsGPT</span>
      </div>

      <!-- Queue Status Badge -->
      <div v-if="queueSize > 0"
           class="queue-badge"
           :data-warning="queueSize >= 5">
        <span class="queue-icon">📸</span>
        <span class="queue-count">{{ queueSize }}</span>
      </div>

      <div class="connection-status" :class="{ connected }">
        <span class="status-pulse"></span>
        <span class="status-text">{{ connected ? 'LIVE' : 'CONNECTING' }}</span>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main">
      <!-- Processing State (hides previous answer) -->
      <div v-if="isProcessing" class="processing">
        <div class="processing-animation">
          <div class="scan-line"></div>
          <div class="processing-icon">🔍</div>
        </div>
        <p class="processing-text">ANALYZING QUESTION</p>
        <div class="processing-dots">
          <span></span><span></span><span></span>
        </div>
      </div>

      <!-- Streaming State -->
      <div v-else-if="isStreaming" class="streaming">
        <!-- Reasoning Display -->
        <div v-if="streamingReasoning" class="streaming-reasoning">
          <div class="reasoning-header">
            <div class="reasoning-title">
              <span class="reasoning-icon">💭</span>
              <span class="reasoning-label">AI REASONING</span>
            </div>
            <!-- Web Search Indicator -->
            <div v-if="isSearching" class="search-indicator">
              <span class="search-icon">🌐</span>
              <span class="search-text">Searching web...</span>
              <div class="search-spinner"></div>
            </div>
            <div class="reasoning-pulse"></div>
          </div>
          <div ref="reasoningContentRef" class="reasoning-content">{{ streamingReasoning }}</div>
        </div>

        <!-- Error Display (if any) -->
        <div v-if="streamingError" class="streaming-error">
          <span class="error-icon">⚠️</span>
          <p>{{ streamingError }}</p>
        </div>
      </div>

      <!-- Waiting State -->
      <div v-else-if="!currentAnswer" class="waiting">
        <div class="waiting-icon">
          <div class="radar-ping"></div>
          <span>📸</span>
        </div>
        <h2 class="waiting-title">READY TO SCAN</h2>
        <p class="waiting-subtitle">Press trigger key or middle mouse button</p>
      </div>

      <!-- Answer Display -->
      <div v-else class="answer-display">
        <!-- Single Choice -->
        <div v-if="parsedAnswer.type === 'single'" class="answer-card single">
          <div class="answer-header">
            <span class="answer-type-badge">SINGLE CHOICE</span>
          </div>
          <div class="single-answer">
            <div class="correct-letter">{{ parsedAnswer.answer }}</div>
            <div v-if="parsedAnswer.options" class="options-list">
              <div
                v-for="(option, idx) in parsedAnswer.options"
                :key="idx"
                class="option-item"
                :class="{ correct: idx === parsedAnswer.correct_index }"
              >
                <span class="option-marker">{{ idx === parsedAnswer.correct_index ? '✓' : '○' }}</span>
                <span class="option-text">{{ option }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Multiple Choice -->
        <div v-else-if="parsedAnswer.type === 'multiple'" class="answer-card multiple">
          <div class="answer-header">
            <span class="answer-type-badge multiple">MULTIPLE CHOICE</span>
            <span class="answer-count">{{ parsedAnswer.answers?.length }} answers</span>
          </div>
          <div class="multiple-answers">
            <div class="correct-letters">
              <span v-for="ans in parsedAnswer.answers" :key="ans" class="letter-chip">{{ ans }}</span>
            </div>
            <div v-if="parsedAnswer.options" class="options-list">
              <div
                v-for="(option, idx) in parsedAnswer.options"
                :key="idx"
                class="option-item"
                :class="{ correct: parsedAnswer.correct_indices?.includes(idx) }"
              >
                <span class="option-marker">{{ parsedAnswer.correct_indices?.includes(idx) ? '✓' : '○' }}</span>
                <span class="option-text">{{ option }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Drag & Drop -->
        <div v-else-if="parsedAnswer.type === 'dragdrop'" class="answer-card dragdrop">
          <div class="answer-header">
            <span class="answer-type-badge dragdrop">DRAG & DROP</span>
          </div>
          <div class="dragdrop-mappings">
            <div v-for="(mapping, idx) in parsedAnswer.mappings" :key="idx" class="mapping-row">
              <div class="mapping-item">{{ mapping.item }}</div>
              <div class="mapping-arrow">→</div>
              <div class="mapping-target">{{ mapping.target }}</div>
            </div>
          </div>
        </div>

        <!-- Hot Area -->
        <div v-else-if="parsedAnswer.type === 'hotarea'" class="answer-card hotarea">
          <div class="answer-header">
            <span class="answer-type-badge hotarea">HOT AREA</span>
            <span class="answer-count">{{ parsedAnswer.selections?.length }} selection{{ parsedAnswer.selections?.length > 1 ? 's' : '' }}</span>
          </div>
          <div class="hotarea-selections">
            <div v-for="(sel, idx) in parsedAnswer.selections" :key="idx" class="hotarea-cell">
              <div class="cell-index">{{ idx + 1 }}</div>
              <div class="cell-content">
                <div class="cell-label">
                  <span class="label-icon">&#x25B6;</span>
                  <span class="label-text">ROW</span>
                </div>
                <div class="cell-value row-value">{{ sel.row }}</div>
              </div>
              <div class="cell-divider"></div>
              <div class="cell-content">
                <div class="cell-label">
                  <span class="label-icon">&#x25BC;</span>
                  <span class="label-text">COL</span>
                </div>
                <div class="cell-value col-value">{{ sel.column }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Sequence -->
        <div v-else-if="parsedAnswer.type === 'sequence'" class="answer-card sequence">
          <div class="answer-header">
            <span class="answer-type-badge sequence">SEQUENCE</span>
          </div>
          <div class="sequence-steps">
            <div v-for="(step, idx) in parsedAnswer.steps" :key="idx" class="sequence-step">
              <div class="step-number">{{ idx + 1 }}</div>
              <div class="step-text">{{ step }}</div>
            </div>
          </div>
        </div>

        <!-- Matching -->
        <div v-else-if="parsedAnswer.type === 'matching'" class="answer-card matching">
          <div class="answer-header">
            <span class="answer-type-badge matching">MATCHING</span>
          </div>
          <div class="matching-pairs">
            <div v-for="(pair, idx) in parsedAnswer.pairs" :key="idx" class="match-pair">
              <div class="match-left">{{ pair.left }}</div>
              <div class="match-connector">
                <svg viewBox="0 0 24 24"><path d="M5 12h14M14 5l7 7-7 7"/></svg>
              </div>
              <div class="match-right">{{ pair.right }}</div>
            </div>
          </div>
        </div>

        <!-- Yes/No -->
        <div v-else-if="parsedAnswer.type === 'yesno'" class="answer-card yesno">
          <div class="answer-header">
            <span class="answer-type-badge yesno">YES / NO</span>
          </div>
          <div class="yesno-statements">
            <div v-for="(item, idx) in parsedAnswer.statements" :key="idx" class="yesno-row">
              <div class="yesno-statement">{{ item.statement }}</div>
              <div class="yesno-answer" :class="item.answer?.toLowerCase()">
                {{ item.answer }}
              </div>
            </div>
          </div>
        </div>

        <!-- Case Study -->
        <div v-else-if="parsedAnswer.type === 'casestudy'" class="answer-card casestudy">
          <div class="answer-header">
            <span class="answer-type-badge casestudy">CASE STUDY</span>
          </div>
          <div v-if="parsedAnswer.context" class="casestudy-context">
            {{ parsedAnswer.context }}
          </div>
          <div class="casestudy-answers">
            <div v-for="(item, idx) in parsedAnswer.answers" :key="idx" class="casestudy-item">
              <div class="casestudy-question">{{ item.question }}</div>
              <div class="casestudy-answer">{{ item.answer }}</div>
            </div>
          </div>
        </div>

        <!-- Error -->
        <div v-else-if="parsedAnswer.type === 'error'" class="answer-card error">
          <div class="answer-header">
            <span class="answer-type-badge error">ERROR</span>
          </div>
          <div class="error-message">
            <span class="error-icon">⚠️</span>
            <p>{{ parsedAnswer.message }}</p>
          </div>
        </div>

        <!-- Fallback (plain text) -->
        <div v-else class="answer-card fallback">
          <div class="answer-header">
            <span class="answer-type-badge">ANSWER</span>
          </div>
          <div class="fallback-text">{{ rawAnswer }}</div>
        </div>

        <!-- Confidence & Verification -->
        <div v-if="parsedAnswer.confidence !== undefined || parsedAnswer.verified" class="confidence-section">
          <div class="confidence-row">
            <div v-if="parsedAnswer.confidence !== undefined" class="confidence-indicator">
              <span class="confidence-label">CONFIDENCE</span>
              <div class="confidence-bar-wrapper">
                <div
                  class="confidence-bar"
                  :style="{ width: `${parsedAnswer.confidence}%` }"
                  :class="confidenceLevel"
                ></div>
              </div>
              <span class="confidence-value" :class="confidenceLevel">{{ parsedAnswer.confidence }}%</span>
            </div>
            <div v-if="parsedAnswer.verified" class="verified-badge">
              <span class="verified-icon">🔍</span>
              <span class="verified-text">WEB VERIFIED</span>
            </div>
          </div>
          <div v-if="parsedAnswer.sources && parsedAnswer.sources.length > 0" class="sources-section">
            <span class="sources-label">Sources:</span>
            <div class="sources-list">
              <a
                v-for="(source, idx) in parsedAnswer.sources"
                :key="idx"
                :href="source"
                target="_blank"
                rel="noopener"
                class="source-link"
              >
                {{ formatSourceUrl(source) }}
              </a>
            </div>
          </div>
        </div>

        <!-- Metadata -->
        <div class="answer-meta">
          <span class="meta-time">{{ formatTimestamp(currentAnswer.timestamp) }}</span>
          <span v-if="currentAnswer.model" class="meta-model">{{ currentAnswer.model }}</span>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="footer">
      <span>Azure Exam Assistant</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useSocket } from './composables/useSocket'
import type { ParsedAnswer } from './types/events'

// Socket.IO connection - replaces all SSE logic!
const { connected, isProcessing, currentAnswer, isStreaming, streamingReasoning, streamingError, isSearching, queueSize } = useSocket()

// Auto-scroll for reasoning content
const reasoningContentRef = ref<HTMLElement | null>(null)

// Watch for reasoning updates and auto-scroll
watch(streamingReasoning, async () => {
  await nextTick()
  if (reasoningContentRef.value) {
    reasoningContentRef.value.scrollTop = reasoningContentRef.value.scrollHeight
  }
})

// Fallback answer type for unparseable JSON
interface FallbackAnswer {
  type: 'fallback'
  text: string
  confidence?: number
  verified?: boolean
  sources?: string[]
}

type FullParsedAnswer = ParsedAnswer | FallbackAnswer

// Raw answer text
const rawAnswer = computed(() => currentAnswer.value?.answer || '')

// Helper to extract letter from answer (handles "A", "A.", "A. Option text", or full option text)
const extractLetter = (answer: string, options?: string[], correctIndex?: number): string => {
  // If it's already a single letter (with optional period)
  const letterMatch = answer.match(/^([A-Z])\.?$/i)
  if (letterMatch) {
    return letterMatch[1].toUpperCase()
  }

  // If we have correct_index, use it to get the letter
  if (typeof correctIndex === 'number') {
    return String.fromCharCode(65 + correctIndex) // 0 -> A, 1 -> B, etc.
  }

  // Try to find the answer in options and get its letter
  if (options && options.length > 0) {
    for (let i = 0; i < options.length; i++) {
      const option = options[i]
      // Check if answer matches the option text (with or without letter prefix)
      const optionText = option.replace(/^[A-Z]\.?\s*/i, '').trim()
      if (answer.toLowerCase() === optionText.toLowerCase() ||
          answer.toLowerCase() === option.toLowerCase()) {
        return String.fromCharCode(65 + i)
      }
    }
  }

  // Fallback: return first letter if answer starts with "A.", "B.", etc.
  const prefixMatch = answer.match(/^([A-Z])[\.\s]/i)
  if (prefixMatch) {
    return prefixMatch[1].toUpperCase()
  }

  // Last resort: return the answer as-is (truncated if too long)
  return answer.length > 3 ? answer.substring(0, 1).toUpperCase() : answer
}

// Parse the JSON answer
const parsedAnswer = computed<FullParsedAnswer>(() => {
  if (!currentAnswer.value?.answer) {
    return { type: 'fallback', text: '' }
  }

  try {
    const parsed = JSON.parse(currentAnswer.value.answer)
    if (parsed.type) {
      // Normalize single choice answer to just the letter
      if (parsed.type === 'single' && parsed.answer) {
        parsed.answer = extractLetter(parsed.answer, parsed.options, parsed.correct_index)
      }
      // Normalize multiple choice answers to just letters
      if (parsed.type === 'multiple' && Array.isArray(parsed.answers)) {
        parsed.answers = parsed.answers.map((ans: string) =>
          extractLetter(ans, parsed.options)
        )
      }
      return parsed
    }
    return { type: 'fallback', text: currentAnswer.value.answer }
  } catch {
    // Not valid JSON, return as fallback text
    return { type: 'fallback', text: currentAnswer.value.answer }
  }
})

const formatTimestamp = (timestamp: string) => {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return timestamp
  }
}

// Confidence level for styling
const confidenceLevel = computed(() => {
  const confidence = parsedAnswer.value.confidence
  if (confidence === undefined) return ''
  if (confidence >= 90) return 'high'
  if (confidence >= 70) return 'medium'
  return 'low'
})

// Format source URL to show just the domain/path
const formatSourceUrl = (url: string) => {
  try {
    const parsed = new URL(url)
    const path = parsed.pathname.length > 30
      ? parsed.pathname.substring(0, 30) + '...'
      : parsed.pathname
    return `${parsed.hostname}${path}`
  } catch {
    return url.length > 40 ? url.substring(0, 40) + '...' : url
  }
}
</script>

<style>
:root {
  --bg-primary: #0a0a0f;
  --bg-secondary: #12121a;
  --bg-card: #1a1a24;
  --bg-elevated: #22222e;

  --accent-cyan: #00f5d4;
  --accent-magenta: #f72585;
  --accent-yellow: #fee440;
  --accent-blue: #4361ee;
  --accent-orange: #ff6b35;
  --accent-green: #7ae582;
  --accent-purple: #9d4edd;

  --text-primary: #ffffff;
  --text-secondary: #a0a0b0;
  --text-muted: #606070;

  --border-subtle: rgba(255,255,255,0.08);
  --border-accent: rgba(0,245,212,0.3);

  --font-mono: 'Space Mono', monospace;
  --font-sans: 'DM Sans', sans-serif;

  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 16px;
}
</style>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(ellipse at 20% 0%, rgba(0,245,212,0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 100%, rgba(247,37,133,0.08) 0%, transparent 50%),
    var(--bg-primary);
}

/* Header */
.header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  background: rgba(10,10,15,0.9);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-subtle);
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.logo-icon {
  font-size: 1.5rem;
}

.logo-text {
  font-family: var(--font-mono);
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-magenta));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  background: var(--bg-elevated);
  border-radius: 100px;
  border: 1px solid var(--border-subtle);
}

.connection-status.connected {
  border-color: var(--accent-green);
  background: rgba(122,229,130,0.1);
}

.status-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-magenta);
  animation: pulse 2s infinite;
}

.connection-status.connected .status-pulse {
  background: var(--accent-green);
}

.status-text {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.connection-status.connected .status-text {
  color: var(--accent-green);
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.9); }
}

/* Queue Status Badge */
.queue-badge {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  background: rgba(254, 228, 64, 0.15);
  border: 1px solid rgba(254, 228, 64, 0.4);
  border-radius: 100px;
  animation: queuePulse 2s ease-in-out infinite;
}

@keyframes queuePulse {
  0%, 100% { box-shadow: 0 0 12px rgba(254, 228, 64, 0.3); }
  50% { box-shadow: 0 0 20px rgba(254, 228, 64, 0.6); }
}

.queue-icon {
  font-size: 0.875rem;
}

.queue-count {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--accent-yellow);
}

.queue-badge[data-warning="true"] {
  background: rgba(247, 37, 133, 0.15);
  border-color: rgba(247, 37, 133, 0.4);
}

.queue-badge[data-warning="true"] .queue-count {
  color: var(--accent-magenta);
}

/* Main */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1.5rem 1rem;
  overflow-y: auto;
}

/* Processing State */
.processing {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
}

.processing-animation {
  position: relative;
  width: 100px;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.scan-line {
  position: absolute;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent);
  animation: scan 1.5s ease-in-out infinite;
}

@keyframes scan {
  0%, 100% { top: 0; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: 100%; opacity: 0; }
}

.processing-icon {
  font-size: 3rem;
  animation: bounce 1s ease-in-out infinite;
}

@keyframes bounce {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.processing-text {
  font-family: var(--font-mono);
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--accent-cyan);
}

.processing-dots {
  display: flex;
  gap: 0.5rem;
}

.processing-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-cyan);
  animation: dotPulse 1.4s infinite ease-in-out;
}

.processing-dots span:nth-child(1) { animation-delay: -0.32s; }
.processing-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* Streaming State */
.streaming {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Reasoning Section - Redesigned */
.streaming-reasoning {
  background: linear-gradient(135deg, rgba(67, 97, 238, 0.15) 0%, rgba(59, 130, 246, 0.08) 100%);
  border: 1px solid rgba(67, 97, 238, 0.25);
  border-radius: var(--radius-lg);
  padding: 0;
  max-height: 400px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow:
    0 0 0 1px rgba(67, 97, 238, 0.1),
    0 4px 24px rgba(67, 97, 238, 0.15);
  animation: reasoningSlideIn 0.4s ease-out;
}

@keyframes reasoningSlideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.reasoning-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1rem;
  background: rgba(67, 97, 238, 0.12);
  border-bottom: 1px solid rgba(67, 97, 238, 0.2);
}

.reasoning-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.reasoning-icon {
  font-size: 1.125rem;
  filter: drop-shadow(0 0 8px rgba(67, 97, 238, 0.5));
  animation: iconFloat 2s ease-in-out infinite;
}

@keyframes iconFloat {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-2px) scale(1.05); }
}

.reasoning-label {
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: #818cf8;
  text-shadow: 0 0 20px rgba(129, 140, 248, 0.5);
}

.reasoning-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #818cf8;
  box-shadow: 0 0 12px rgba(129, 140, 248, 0.8);
  animation: pulse 1.8s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
    box-shadow: 0 0 12px rgba(129, 140, 248, 0.8);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.3);
    box-shadow: 0 0 20px rgba(129, 140, 248, 1);
  }
}

/* Web Search Indicator - Enhanced */
.search-indicator {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 20px;
  font-size: 0.75rem;
  color: #4ade80;
  box-shadow: 0 0 12px rgba(34, 197, 94, 0.2);
  animation: searchPulse 2s ease-in-out infinite;
}

@keyframes searchPulse {
  0%, 100% {
    box-shadow: 0 0 12px rgba(34, 197, 94, 0.2);
  }
  50% {
    box-shadow: 0 0 20px rgba(34, 197, 94, 0.4);
  }
}

.search-indicator .search-icon {
  font-size: 0.875rem;
  animation: searchBounce 1.5s ease-in-out infinite;
}

@keyframes searchBounce {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  25% { transform: translateY(-3px) rotate(-5deg); }
  75% { transform: translateY(-1px) rotate(5deg); }
}

.search-text {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 0.6875rem;
  letter-spacing: 0.05em;
}

.search-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(74, 222, 128, 0.3);
  border-top-color: #4ade80;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Reasoning Content - Enhanced */
.reasoning-content {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 0.8125rem;
  line-height: 1.7;
  color: #a5b4fc;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
  padding: 1rem;
  scroll-behavior: smooth;
  background: rgba(15, 23, 42, 0.3);
}

/* Custom scrollbar for reasoning content */
.reasoning-content::-webkit-scrollbar {
  width: 6px;
}

.reasoning-content::-webkit-scrollbar-track {
  background: rgba(67, 97, 238, 0.05);
  border-radius: 3px;
}

.reasoning-content::-webkit-scrollbar-thumb {
  background: rgba(67, 97, 238, 0.4);
  border-radius: 3px;
}

.reasoning-content::-webkit-scrollbar-thumb:hover {
  background: rgba(67, 97, 238, 0.6);
}

/* Streaming Error */
.streaming-error {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  color: #fca5a5;
}

.streaming-error .error-icon {
  font-size: 1.25rem;
}

.streaming-error p {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.875rem;
}

/* Waiting State */
.waiting {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  text-align: center;
}

.waiting-icon {
  position: relative;
  font-size: 4rem;
  margin-bottom: 1rem;
}

.radar-ping {
  position: absolute;
  inset: -20px;
  border: 2px solid var(--accent-cyan);
  border-radius: 50%;
  animation: radarPing 2s ease-out infinite;
}

@keyframes radarPing {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(1.5); opacity: 0; }
}

.waiting-title {
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-primary);
}

.waiting-subtitle {
  font-size: 0.875rem;
  color: var(--text-muted);
}

/* Answer Display */
.answer-display {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  animation: slideUp 0.4s ease-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Answer Card Base */
.answer-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
  overflow: hidden;
}

.answer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1rem;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-subtle);
}

.answer-type-badge {
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 0.25rem 0.625rem;
  border-radius: 4px;
  background: var(--accent-cyan);
  color: var(--bg-primary);
}

.answer-type-badge.multiple { background: var(--accent-magenta); }
.answer-type-badge.dragdrop { background: var(--accent-blue); }
.answer-type-badge.hotarea { background: var(--accent-orange); }
.answer-type-badge.sequence { background: var(--accent-purple); }
.answer-type-badge.matching { background: var(--accent-yellow); color: var(--bg-primary); }
.answer-type-badge.yesno { background: var(--accent-green); color: var(--bg-primary); }
.answer-type-badge.casestudy { background: #6366f1; }
.answer-type-badge.error { background: var(--accent-magenta); }

.answer-count {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Single Choice */
.single-answer {
  padding: 1.5rem 1rem;
}

.correct-letter {
  font-family: var(--font-mono);
  font-size: 4rem;
  font-weight: 700;
  text-align: center;
  color: var(--accent-cyan);
  text-shadow: 0 0 40px rgba(0,245,212,0.5);
  margin-bottom: 1.5rem;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.option-item.correct {
  background: rgba(0,245,212,0.1);
  border-color: var(--accent-cyan);
}

.option-marker {
  flex-shrink: 0;
  width: 1.5rem;
  height: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  border-radius: 50%;
  background: var(--bg-elevated);
  color: var(--text-muted);
}

.option-item.correct .option-marker {
  background: var(--accent-cyan);
  color: var(--bg-primary);
  font-weight: 700;
}

.option-text {
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.option-item.correct .option-text {
  color: var(--text-primary);
  font-weight: 500;
}

/* Multiple Choice */
.multiple-answers {
  padding: 1.5rem 1rem;
}

.correct-letters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.letter-chip {
  font-family: var(--font-mono);
  font-size: 1.5rem;
  font-weight: 700;
  padding: 0.5rem 1rem;
  background: linear-gradient(135deg, var(--accent-magenta), var(--accent-purple));
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 20px rgba(247,37,133,0.3);
}

/* Drag & Drop */
.dragdrop-mappings {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.mapping-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.mapping-item {
  flex: 1;
  font-size: 0.875rem;
  padding: 0.625rem 0.875rem;
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  border: 1px dashed var(--accent-blue);
  color: var(--text-primary);
}

.mapping-arrow {
  font-size: 1.25rem;
  color: var(--accent-blue);
  font-weight: 700;
}

.mapping-target {
  flex: 1;
  font-size: 0.875rem;
  padding: 0.625rem 0.875rem;
  background: rgba(67,97,238,0.2);
  border-radius: var(--radius-sm);
  border: 1px solid var(--accent-blue);
  color: var(--accent-blue);
  font-weight: 500;
}

/* Hot Area - Mobile First */
.hotarea-selections {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.hotarea-cell {
  display: flex;
  align-items: stretch;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  position: relative;
}

.cell-index {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 2.5rem;
  background: var(--accent-orange);
  color: var(--bg-primary);
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1rem;
}

.cell-content {
  flex: 1;
  padding: 0.875rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.cell-label {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.625rem;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.label-icon {
  font-size: 0.5rem;
  color: var(--accent-orange);
}

.cell-value {
  font-family: var(--font-mono);
  font-size: 0.9375rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text-primary);
  word-break: break-word;
}

.row-value {
  color: var(--accent-orange);
}

.col-value {
  color: var(--text-primary);
}

.cell-divider {
  width: 1px;
  background: linear-gradient(
    to bottom,
    transparent,
    var(--accent-orange),
    transparent
  );
  opacity: 0.4;
}

/* Sequence */
.sequence-steps {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sequence-step {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--accent-purple);
}

.step-number {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.875rem;
  background: var(--accent-purple);
  color: white;
  border-radius: 50%;
}

.step-text {
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--text-primary);
  padding-top: 0.25rem;
}

/* Matching */
.matching-pairs {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.match-pair {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.875rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.match-left {
  flex: 1;
  font-size: 0.875rem;
  padding: 0.5rem 0.75rem;
  background: rgba(254,228,64,0.15);
  border-radius: var(--radius-sm);
  color: var(--accent-yellow);
  font-weight: 500;
}

.match-connector {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}

.match-connector svg {
  width: 100%;
  height: 100%;
  fill: none;
  stroke: var(--accent-yellow);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.match-right {
  flex: 1;
  font-size: 0.875rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
}

/* Yes/No */
.yesno-statements {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.yesno-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.yesno-statement {
  flex: 1;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.yesno-answer {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  padding: 0.375rem 0.875rem;
  border-radius: 100px;
  text-transform: uppercase;
}

.yesno-answer.yes {
  background: rgba(122,229,130,0.2);
  color: var(--accent-green);
  border: 1px solid var(--accent-green);
}

.yesno-answer.no {
  background: rgba(247,37,133,0.2);
  color: var(--accent-magenta);
  border: 1px solid var(--accent-magenta);
}

/* Case Study */
.casestudy-context {
  padding: 1rem;
  background: var(--bg-secondary);
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-subtle);
}

.casestudy-answers {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.casestudy-item {
  padding: 1rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border-left: 3px solid #6366f1;
}

.casestudy-question {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.casestudy-answer {
  font-size: 1rem;
  font-weight: 500;
  color: var(--text-primary);
}

/* Error */
.error-message {
  padding: 2rem 1rem;
  text-align: center;
}

.error-icon {
  font-size: 3rem;
  display: block;
  margin-bottom: 1rem;
}

.error-message p {
  color: var(--text-secondary);
  font-size: 0.9375rem;
}

/* Fallback */
.fallback-text {
  padding: 1.5rem 1rem;
  font-size: 1.125rem;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Confidence Section */
.confidence-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 1rem;
  border: 1px solid var(--border-subtle);
}

.confidence-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.confidence-indicator {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 200px;
}

.confidence-label {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.confidence-bar-wrapper {
  flex: 1;
  height: 6px;
  background: var(--bg-elevated);
  border-radius: 3px;
  overflow: hidden;
}

.confidence-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.confidence-bar.high {
  background: linear-gradient(90deg, var(--accent-green), #4ade80);
}

.confidence-bar.medium {
  background: linear-gradient(90deg, var(--accent-yellow), #fbbf24);
}

.confidence-bar.low {
  background: linear-gradient(90deg, var(--accent-magenta), #f87171);
}

.confidence-value {
  font-family: var(--font-mono);
  font-size: 0.875rem;
  font-weight: 700;
  min-width: 3rem;
  text-align: right;
}

.confidence-value.high { color: var(--accent-green); }
.confidence-value.medium { color: var(--accent-yellow); }
.confidence-value.low { color: var(--accent-magenta); }

.verified-badge {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  background: rgba(67,97,238,0.15);
  border: 1px solid var(--accent-blue);
  border-radius: 100px;
}

.verified-icon {
  font-size: 0.875rem;
}

.verified-text {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--accent-blue);
}

.sources-section {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
}

.sources-label {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  display: block;
  margin-bottom: 0.5rem;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.source-link {
  font-size: 0.75rem;
  color: var(--accent-cyan);
  text-decoration: none;
  padding: 0.25rem 0.5rem;
  background: rgba(0,245,212,0.1);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-link:hover {
  background: rgba(0,245,212,0.2);
  color: var(--text-primary);
}

/* Metadata */
.answer-meta {
  display: flex;
  justify-content: space-between;
  padding: 0.75rem 0;
  border-top: 1px solid var(--border-subtle);
  margin-top: 0.5rem;
}

.meta-time, .meta-model {
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  text-transform: uppercase;
}

/* Footer */
.footer {
  padding: 1rem;
  text-align: center;
  font-size: 0.75rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border-subtle);
}

/* Responsive */
@media (min-width: 640px) {
  .main {
    padding: 2rem;
    max-width: 600px;
    margin: 0 auto;
    width: 100%;
  }

  .correct-letter {
    font-size: 5rem;
  }
}
</style>
