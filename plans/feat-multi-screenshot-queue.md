# Multi-Screenshot Queue for ExamsGPT

## Overview

Add support for capturing multiple screenshots and analyzing them together as a single question. This addresses the limitation where some exam questions require scrolling to see all answer choices or case study context.

**Problem:** Current implementation captures only one screenshot per trigger. Some questions have content outside the visible viewport.

**Solution:** Add queue-based workflow with dedicated keys for queueing and sending multiple screenshots.

---

## Proposed Solution

### User Workflow

1. **Single screenshot (existing)**: Press `=` → capture & analyze immediately
2. **Queue screenshots**: Press `-` → add to queue (no immediate analysis)
3. **Send queue**: Press `0` → analyze all queued screenshots together
4. **Queue count shown in UI**: Frontend displays badge with queued screenshot count

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Dedicated keys** (`-` to queue, `0` to send) | Clear mental model, explicit user intent |
| **Keep single-shot workflow** | Backward compatible, existing users unaffected |
| **Soft limit at 5+** | Warning for unusually large queues, no hard restriction |
| **Queue & Send only** | Simple, no clear/undo needed (YAGNI) |
| **AI analyzes all as one question** | Both OpenAI & Gemini support multiple images per request |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Input                              │
│  trigger_key (existing '=') │ queue_key (new '-') │ send_key (new '0') │
└─────────────────────┬─────────────────┬───────────────────────┘
                      │                 │
                      ▼                 ▼
         ┌──────────────────────────────────────────┐
         │           CaptureManager                  │
         │  - trigger_key → handle_screenshot()      │
         │  - queue_key → handle_queue_add()         │
         │  - send_key → handle_queue_send()         │
         └──────────────┬────────────────────────────┘
                        │
        ┌───────────────┼───────────────────────┐
        ▼               ▼                       ▼
┌──────────────┐  ┌──────────────┐      ┌─────────────┐
│ AIService    │  │ ScreenshotQueue│     │ OutputHandler│
│ .analyze()   │  │ .add()        │      │ .send_queue_│
│              │  │ .get_all()    │      │    status()  │
└──────────────┘  └───────┬───────┘      └──────┬───────┘
                          │                     │
                          ▼                     ▼
                  ┌───────────────┐      ┌─────────────┐
                  │ In-memory     │      │ Webhook     │
                  │ queue storage │      │ Socket.IO   │
                  └───────────────┘      └──────┬──────┘
                                                 │
                                                 ▼
                                         ┌───────────────┐
                                         │ Frontend UI   │
                                         │ Queue Badge   │
                                         └───────────────┘
```

---

## Implementation Plan

### Phase 1: Core Queue Infrastructure

**Files:**
- `src/screenshot_queue.py` (NEW)
- `src/config.py`
- `config.yaml`

#### Create ScreenshotQueue class

**File: `src/screenshot_queue.py`**

```python
"""
Screenshot queue management for multi-image analysis
"""
import logging
from datetime import datetime
from typing import Optional, tuple
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenshotQueue:
    """Manages a queue of screenshots for multi-image analysis"""

    def __init__(self, max_warning_size: int = 5):
        self.queue: list[tuple[Image.Image, Optional[str]]] = []
        self.max_warning_size = max_warning_size
        self.created_at: datetime = None

    def add(self, image: Image.Image, path: Optional[str]) -> int:
        """Add screenshot to queue, return current size"""
        try:
            self.queue.append((image, path))
            size = len(self.queue)

            if size >= self.max_warning_size:
                logger.warning(
                    f"Queue size: {size} - ensure these are for the same question"
                )

            return size

        except Exception as e:
            logger.error(f"Failed to add screenshot to queue: {e}")
            raise

    def clear(self) -> int:
        """Clear queue, return number of items cleared"""
        count = len(self.queue)
        self.queue.clear()
        return count

    def get_all(self) -> list[tuple[Image.Image, Optional[str]]]:
        """Get all queued items and clear queue"""
        items = self.queue.copy()
        self.queue.clear()
        return items

    def size(self) -> int:
        """Return current queue size"""
        return len(self.queue)

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.queue) == 0
```

#### Configuration

**File: `src/config.py`** - Add to Config class `__init__`:

```python
# Keyboard Configuration (around line 71)
self.trigger_key = self.yaml_config['keyboard']['trigger_key']
self.queue_key = self.yaml_config['keyboard'].get('queue_key', None)
self.send_key = self.yaml_config['keyboard'].get('send_key', None)
```

**File: `config.yaml`**:

```yaml
keyboard:
  trigger_key: '='      # Existing: immediate analysis
  queue_key: '-'        # NEW: add to queue
  send_key: '0'         # NEW: send queue for analysis
```

---

### Phase 2: CaptureManager Extensions

**File: `src/capture.py`**

#### Update CaptureManager class

```python
class CaptureManager:
    def __init__(self,
                 on_screenshot_callback: Callable,    # existing
                 on_queue_add_callback: Callable,     # NEW
                 on_queue_send_callback: Callable):   # NEW

        self.config = get_config()
        self.screen_capture = ScreenCapture()
        self.keyboard_listener = KeyboardListener(on_trigger=self._handle_trigger)
        self.on_screenshot_callback = on_screenshot_callback

        # NEW: Queue key listeners (if configured)
        self.queue_key_listener: Optional[KeyboardListener] = None
        self.send_key_listener: Optional[KeyboardListener] = None

        if self.config.queue_key:
            self.queue_key_listener = KeyboardListener(
                on_trigger=self._handle_queue_add,
                trigger_key=self.config.queue_key
            )
            logger.info(f"Queue listener initialized with key: {self.config.queue_key}")

        if self.config.send_key:
            self.send_key_listener = KeyboardListener(
                on_trigger=self._handle_queue_send,
                trigger_key=self.config.send_key
            )
            logger.info(f"Send listener initialized with key: {self.config.send_key}")

        # Existing mouse listener
        self.mouse_listener: Optional[MouseListener] = None
        if self.config.enable_middle_button:
            self.mouse_listener = MouseListener(on_trigger=self._handle_trigger)

    def _handle_queue_add(self):
        """Handle queue key press - add screenshot to queue"""
        try:
            logger.info("Queue key activated - capturing screenshot for queue")
            img, saved_path = self.screen_capture.capture_fullscreen()
            self.on_queue_add_callback(img, saved_path)
        except Exception as e:
            logger.error(f"Error handling queue add: {e}")

    def _handle_queue_send(self):
        """Handle send key press - send queue for analysis"""
        try:
            logger.info("Send key activated - processing queue")
            self.on_queue_send_callback()
        except Exception as e:
            logger.error(f"Error handling queue send: {e}")

    def start(self):
        """Start the capture manager (all listeners)"""
        logger.info("Starting CaptureManager...")
        self.keyboard_listener.start()
        if self.queue_key_listener:
            self.queue_key_listener.start()
        if self.send_key_listener:
            self.send_key_listener.start()
        if self.mouse_listener:
            self.mouse_listener.start()

    def stop(self):
        """Stop the capture manager"""
        logger.info("Stopping CaptureManager...")
        self.keyboard_listener.stop()
        if self.queue_key_listener:
            self.queue_key_listener.stop()
        if self.send_key_listener:
            self.send_key_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()

    def is_running(self) -> bool:
        return self.keyboard_listener.running
```

#### Update KeyboardListener for configurable trigger

```python
class KeyboardListener:
    def __init__(self, on_trigger: Callable, trigger_key: str = None):
        self.on_trigger = on_trigger
        self.listener: Optional[keyboard.Listener] = None
        self.running = False

        # Use provided trigger_key or get from config
        if trigger_key:
            self.trigger_key = trigger_key
        else:
            config = get_config()
            self.trigger_key = self._parse_trigger_key(config.trigger_key)

        logger.info(f"Keyboard listener initialized with trigger: {self.trigger_key}")
```

---

### Phase 3: AI Service Multi-Image Support

**File: `src/ai_service.py`**

#### Main entry point

```python
def analyze_multi_screenshots(self, screenshots: list[tuple[Image.Image, Optional[str]]]) -> dict:
    """
    Analyze multiple screenshots as one combined question
    Works with both OpenAI (Responses/Completions) and Gemini

    Args:
        screenshots: List of (Image, path) tuples

    Returns:
        dict: Contains 'answer', 'model', 'timestamp', 'success', and optional 'error'
    """
    try:
        if not screenshots:
            return {
                'success': False,
                'answer': None,
                'error': 'No screenshots provided',
                'timestamp': datetime.now().isoformat()
            }

        start_time = datetime.now()
        provider = self.config.ai_provider
        image_count = len(screenshots)

        logger.info(f"Sending {image_count} screenshots to {provider} for combined analysis...")

        images = [img for img, _ in screenshots]
        paths = [path for _, path in screenshots]

        # Route to appropriate provider
        if self._uses_gemini():
            result = self._analyze_multiple_with_gemini(images, paths, start_time)
        elif self._uses_responses_api():
            result = self._analyze_multiple_with_responses_api(images, paths, start_time)
        else:
            result = self._analyze_multiple_with_completions_api(images, paths, start_time)

        return result

    except Exception as e:
        logger.error(f"Error analyzing multiple screenshots: {e}")
        model = self.config.gemini_model if self._uses_gemini() else self.config.openai_model
        return {
            'success': False,
            'answer': None,
            'model': model,
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }
```

#### OpenAI Responses API (multiple images)

```python
def _analyze_multiple_with_responses_api(self, images: list[Image.Image], paths: list[str], start_time: datetime) -> dict:
    """Analyze multiple images using Responses API (GPT-5.x)"""
    # Convert all images to base64
    image_items = [
        {
            "type": "input_image",
            "image_url": f"data:image/png;base64,{self._image_to_base64(img)}"
        }
        for img in images
    ]

    api_params = {
        "model": self.config.openai_model,
        "input": [{
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": self._get_multi_image_prompt(len(images))},
                *image_items  # Multiple images
            ]
        }],
        "text": {"format": {"type": "text"}, "verbosity": "low"},
        "reasoning": self.config.openai_reasoning,
        "store": self.config.openai_store
    }

    if self.config.openai_tools:
        api_params["tools"] = self.config.openai_tools
    if self.config.openai_include:
        api_params["include"] = self.config.openai_include

    response = self.client.responses.create(**api_params)

    # Extract answer (same logic as single-image)
    answer = None
    for output_item in response.output:
        if output_item.type == 'message' and output_item.content:
            answer = output_item.content[0].text.strip()
            break

    elapsed_time = (datetime.now() - start_time).total_seconds()

    return {
        'success': True,
        'answer': answer,
        'model': self.config.openai_model,
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': elapsed_time,
        'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
    }
```

#### OpenAI Completions API (multiple images)

```python
def _analyze_multiple_with_completions_api(self, images: list[Image.Image], paths: list[str], start_time: datetime) -> dict:
    """Analyze multiple images using Completions API (GPT-4o)"""
    # Convert all images to base64
    image_content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{self._image_to_base64(img)}",
                "detail": "high"
            }
        }
        for img in images
    ]

    response = self.client.chat.completions.create(
        model=self.config.openai_model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": self._get_multi_image_prompt(len(images))},
                *image_content  # Multiple images
            ]
        }],
        max_tokens=self.config.openai_max_tokens,
        temperature=self.config.openai_temperature
    )

    answer = response.choices[0].message.content.strip()
    elapsed_time = (datetime.now() - start_time).total_seconds()

    return {
        'success': True,
        'answer': answer,
        'model': self.config.openai_model,
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': elapsed_time,
        'tokens_used': response.usage.total_tokens if hasattr(response, 'usage') else None
    }
```

#### Gemini (multiple images)

```python
def _analyze_multiple_with_gemini(self, images: list[Image.Image], paths: list[str], start_time: datetime) -> dict:
    """Analyze multiple images using Gemini API"""
    from google.genai import types

    client = _get_gemini_client()

    # Gemini accepts multiple images in contents array
    contents = [
        self._get_multi_image_prompt(len(images)),
        *images  # Multiple PIL images
    ]

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
        tools=[types.Tool(google_search=types.GoogleSearch())],
        response_mime_type="application/json",
    )

    response = client.models.generate_content(
        model=self.config.gemini_model,
        contents=contents,
        config=config
    )

    answer = response.text.strip() if response.text else None
    elapsed_time = (datetime.now() - start_time).total_seconds()

    tokens_used = None
    if hasattr(response, 'usage_metadata'):
        tokens_used = response.usage_metadata.total_token_count

    return {
        'success': True,
        'answer': answer,
        'model': self.config.gemini_model,
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': elapsed_time,
        'tokens_used': tokens_used
    }
```

#### Multi-image prompt modifier

```python
def _get_multi_image_prompt(self, image_count: int) -> str:
    """Get prompt modified for multi-image analysis"""
    base_prompt = self.prompt_template

    multi_instruction = f"""

IMPORTANT: You are receiving {image_count} screenshots that form ONE complete exam question.
These screenshots show different sections of the same question (scroll captures).
Analyze ALL images together to understand the complete question before answering.
Consider the context from all images when determining the answer."""

    return base_prompt + multi_instruction
```

---

### Phase 4: Output Handler Queue Status

**File: `src/output_handler.py`**

#### Add queue status to all output strategies

```python
class OutputStrategy(ABC):
    @abstractmethod
    def send(self, result: dict, screenshot_path: Optional[str] = None):
        pass

    def send_processing(self):
        pass

    def send_queue_status(self, queue_size: int):  # NEW
        pass
```

#### Webhook implementations

```python
class WebhookOutput(OutputStrategy):
    def send_queue_status(self, queue_size: int):
        """Send current queue count to frontend"""
        try:
            payload = {
                'type': 'queue_status',
                'queue_size': queue_size,
                'timestamp': datetime.now().isoformat()
            }
            self._send_with_retry(payload, "queue status")
        except Exception as e:
            logger.error(f"Error sending queue status: {e}")


class StreamingWebhookOutput(WebhookOutput):
    def send_queue_status(self, queue_size: int):
        """Send current queue count to frontend (streaming variant)"""
        # Same implementation as parent
        super().send_queue_status(queue_size)


class ConsoleOutput(OutputStrategy):
    def send_queue_status(self, queue_size: int):
        """Print queue status to console"""
        if queue_size > 0:
            print(f"\n📸 Queue: {queue_size} screenshot(s) queued")
        else:
            print(f"\n✓ Queue cleared")


class SocketIOOutput(OutputStrategy):
    def send_queue_status(self, queue_size: int):
        """Send queue status via Socket.IO (if implemented)"""
        # Future: self.socketio.emit('queue_status', {'queue_size': queue_size})
        logger.debug(f"SocketIO queue status not implemented: {queue_size}")
```

---

### Phase 5: Main Application Integration

**File: `main.py`**

```python
class ExamsGPT:
    def __init__(self):
        # ... existing init ...

        # NEW: Create screenshot queue
        from src.screenshot_queue import ScreenshotQueue
        self.screenshot_queue = ScreenshotQueue()

        # Initialize output handler
        self.output_handler = OutputHandler()

        # Get streaming callback
        streaming_callback = self.output_handler.get_streaming_callback()

        # Initialize AI service
        self.ai_service = AIService(streaming_callback=streaming_callback)

        # NEW: Initialize capture manager with queue callbacks
        self.capture_manager = CaptureManager(
            on_screenshot_callback=self.handle_screenshot,
            on_queue_add_callback=self.handle_queue_add,
            on_queue_send_callback=self.handle_queue_send
        )

        # ... rest of existing init ...

    def handle_queue_add(self, image: Image.Image, screenshot_path: Optional[str]):
        """Handle adding screenshot to queue"""
        try:
            size = self.screenshot_queue.add(image, screenshot_path)
            self.output_handler.send_queue_status(size)
            logger.info(f"Screenshot added to queue. Size: {size}")

        except Exception as e:
            logger.error(f"Error adding to queue: {e}")

    def handle_queue_send(self):
        """Handle sending queued screenshots"""
        try:
            screenshots = self.screenshot_queue.get_all()

            if not screenshots:
                logger.warning("Send triggered but queue is empty")
                self.output_handler.send_queue_status(0)
                return

            # Reset UI queue status
            self.output_handler.send_queue_status(0)

            # Notify processing
            self.output_handler.send_processing()

            # Analyze with AI
            result = self.ai_service.analyze_multi_screenshots(screenshots)

            # Handle output
            first_path = screenshots[0][1] if screenshots[0] else None
            self.output_handler.handle_result(result, first_path)

        except Exception as e:
            logger.error(f"Error processing queue: {e}")
            self.output_handler.handle_result({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    def start(self):
        """Start the application"""
        # ... existing startup code ...

        # Print instructions with new keys
        print("=" * 70)
        print("ExamsGPT is running!")
        print("=" * 70)
        print(f"Press '{self.config.trigger_key}' to capture and analyze (single)")
        if self.config.queue_key:
            print(f"Press '{self.config.queue_key}' to add to queue")
        if self.config.send_key:
            print(f"Press '{self.config.send_key}' to send queue for analysis")
        if self.config.enable_middle_button:
            print("Or click the middle mouse button (scroll wheel)")
        print("Press Ctrl+C to stop")
        print("=" * 70)
        print()
```

---

### Phase 6: Frontend Integration

#### Type definitions

**File: `frontend/src/types/events.ts`**

```typescript
// Add after ProcessingData (around line 18)
export interface QueueStatusData {
  type: 'queue_status'
  queue_size: number
  timestamp: string
}

// Update EventData union (line 40)
export type EventData = AnswerData | ProcessingData | StreamingChunkData | StreamingCompleteData | QueueStatusData
```

#### Socket integration

**File: `frontend/src/composables/useSocket.ts`**

```typescript
// Add to state (around line 23)
const queueSize = ref<number>(0)

// Add socket handler (around line 195, before 'answer' handler)
socket.on('queue_status', (data: QueueStatusData) => {
  console.log('[Socket.IO] Queue status:', data.queue_size)
  queueSize.value = data.queue_size
})

// Update return statement (line 214)
return {
  connected,
  isProcessing,
  currentAnswer,
  isStreaming,
  streamingContent,
  streamingReasoning,
  streamingError,
  isSearching,
  queueSize  // NEW
}
```

#### UI Component

**File: `frontend/src/App.vue`**

**Template (header section, around line 5-13):**
```vue
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
```

**Script (update import, around line 291):**
```typescript
const { connected, isProcessing, currentAnswer, isStreaming, streamingReasoning, streamingError, isSearching, queueSize } = useSocket()
```

**Styles (add after .connection-status, around line 537):**
```css
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
```

---

## Acceptance Criteria

- [x] Pressing `queue_key` (`-`) adds screenshot to queue without triggering analysis
- [x] Pressing `send_key` (`0`) sends all queued screenshots for combined analysis
- [x] Frontend displays queue count badge when screenshots are queued
- [x] Queue badge shows warning style when 5+ screenshots queued
- [x] Queue badge disappears when queue is sent (count = 0)
- [x] Both OpenAI and Gemini analyze multiple images as one question
- [x] Single-shot workflow (`=` key) continues to work as before
- [x] Console output shows queue size in dev mode
- [x] Multi-image prompt instructs AI to consider all screenshots together
- [x] Configuration file allows customizing queue/send keys

---

## Configuration

### Default Keys (config.yaml)

```yaml
keyboard:
  trigger_key: '='      # Single screenshot (existing)
  queue_key: '-'        # Add to queue
  send_key: '0'         # Send queue
```

### Alternative Key Options

Users can customize based on preference:
- Modifier style: `shift+q`, `ctrl+s` (requires KeyboardListener enhancement)
- Function keys: `f1`, `f2` (already supported)
- Number keys: `1`, `2`, `3` (already supported)

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Send pressed with empty queue | Log warning, send `queue_size: 0` to frontend |
| AI API error during multi-image analysis | Return error dict, send to frontend |
| Queue size reaches 5+ | Log warning, show warning style in UI |
| Webhook down when queue status sent | Retry with exponential backoff (existing logic) |
| Invalid/unconfigured queue keys | Skip listener initialization, log info |

---

## Success Metrics

- **User flow**: Users can successfully queue 2-3 screenshots and receive combined analysis
- **Backward compatibility**: Existing single-shot workflow unchanged
- **API compatibility**: Both OpenAI and Gemini return valid answers for multi-image requests
- **UI responsiveness**: Queue count updates within 100ms of key press
- **Error recovery**: Graceful handling of edge cases (empty queue, API failures)

---

## References & Research

### Internal References
- Current capture implementation: [src/capture.py](src/capture.py)
- AI service provider routing: [src/ai_service.py:95-104](src/ai_service.py#L95-L104)
- Output strategy pattern: [src/output_handler.py](src/output_handler.py)
- Frontend socket integration: [frontend/src/composables/useSocket.ts](frontend/src/composables/useSocket.ts)

### API Documentation
- OpenAI Vision API: Multiple images supported in `messages[].content[]` array
- Gemini Vision API: Multiple images supported in `contents` array
- Both APIs accept PIL Images (Gemini) or base64 (OpenAI)

### Related Work
- Screenshot optimization (WebP/JPEG): commits 4603512, 34436e8
- Streaming implementation: commits c19ef73, 4a778be

---

## Future Considerations

### Potential Enhancements (Out of Scope)
- **Queue preview**: Show thumbnails of queued screenshots in UI
- **Reorder queue**: Drag and drop to change screenshot order
- **Individual removal**: Remove specific screenshot from queue
- **Auto-send timer**: Automatically send queue after N seconds of inactivity
- **Stitching**: Combine screenshots into single image before sending (not needed - APIs support multiple images)

### Extensibility
- Queue pattern could be used for other batch operations
- Queue state could be persisted to disk for crash recovery
- WebSocket-based queue sync for multiple frontend instances
