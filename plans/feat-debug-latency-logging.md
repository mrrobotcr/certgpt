# feat: Add Debug Latency Logging with Phase Breakdown

## Overview

Add debug-level latency logging to OpenAI and Gemini API calls with phase breakdown (setup, network, parsing) and time-to-first-token (TTFT) tracking for streaming responses.

`★ Insight ─────────────────────────────────────`
**Why this matters:** API latency optimization requires knowing which phase is slow. Current implementation only logs total elapsed time, making it impossible to distinguish between slow preprocessing, network issues, or parsing overhead.
`─────────────────────────────────────────────────`

## Problem Statement

**Current State:**
- [src/ai_service.py](src/ai_service.py) tracks only total elapsed time using `datetime.now()`
- Logs show: `"Analysis complete in 21.22s - Tokens used: 3601"`
- No visibility into where time is spent (setup vs network vs parsing)
- Streaming responses don't track time-to-first-token (TTFT)

**Impact:**
- Cannot diagnose performance bottlenecks
- Cannot compare OpenAI vs Gemini latency fairly
- Streaming performance issues (slow TTFT) are invisible
- No data for optimization decisions

## Proposed Solution

Add debug-level latency instrumentation with:
1. **Three phase breakdown:** Request setup → Network → Response parsing
2. **Time-to-first-token (TTFT):** For streaming responses
3. **Zero overhead when disabled:** Guarded by `logger.isEnabledFor(logging.DEBUG)`
4. **Nanosecond precision:** Using `time.perf_counter_ns()`
5. **Structured logging:** Machine-parseable format for analysis

### Phase Definitions

| Phase | Start | End | What's Measured |
|-------|-------|-----|-----------------|
| **Request Setup** | Before API prep | Before `client.create()` | Image conversion, parameter construction |
| **Network** | Before `client.create()` | After response received (or first chunk for streaming) | API round-trip time |
| **Response Parsing** | After response received | After answer extraction | JSON parsing, validation, usage extraction |
| **TTFT** (streaming only) | Before `client.create()` | First content delta | User-perceived responsiveness |

## Technical Approach

### Architecture

**No new files required** - modifications to existing files only:

```
src/
├── config.py              # Add latency config options
├── ai_service.py          # Add timing to 5 API methods
└── output_handler.py      # Optional: structured formatter

config.yaml                # Add debug_latency flag
```

### Implementation Plan

#### Phase 1: Configuration (Zero Overhead Foundation)

**File:** [src/config.py](src/config.py)

Add new configuration options:

```python
@dataclass
class LoggingConfig:
    level: str = 'INFO'
    save_to_file: bool = True
    directory: str = 'logs'
    save_history: bool = True
    # NEW:
    debug_latency: bool = False          # Enable phase breakdown logging
    latency_precision: str = 'ms'        # 'ns' | 'ms' | 'both'
    latency_format: str = 'text'         # 'text' | 'json'
```

**File:** [config.yaml](config.yaml)

```yaml
logging:
  level: 'INFO'
  save_to_file: true
  directory: 'logs'
  save_history: true
  # NEW:
  debug_latency: false       # Set to true for phase breakdown logging
  latency_precision: 'ms'    # Display precision: 'ns', 'ms', or 'both'
  latency_format: 'text'     # Log format: 'text' or 'json'
```

#### Phase 2: Latency Tracking Context Manager

**File:** [src/ai_service.py](src/ai_service.py) (add at top after imports)

```python
import time
from contextlib import contextmanager
from typing import Dict, Any, Optional

@contextmanager
def measure_latency(operation_name: str, logger, enabled: bool = True):
    """
    Context manager for measuring API call latency with phase breakdown.

    Zero overhead when disabled: only runs timing code if enabled=True
    and logger level is DEBUG.
    """
    if not enabled or not logger.isEnabledFor(logging.DEBUG):
        yield {'mark': lambda name: None}
        return

    phases: Dict[str, int] = {}  # nanoseconds
    start_ns = time.perf_counter_ns()

    class PhaseTimer:
        def mark(self, phase_name: str) -> None:
            """Mark a phase completion time relative to start (in nanoseconds)"""
            phases[phase_name] = time.perf_counter_ns() - start_ns

    try:
        yield PhaseTimer()
    finally:
        total_ns = time.perf_counter_ns() - start_ns

        # Convert to milliseconds for display
        phases_ms = {k: v / 1_000_000 for k, v in phases.items()}
        total_ms = total_ns / 1_000_000

        logger.debug(
            f"[LATENCY] {operation_name} | total={total_ms:.2f}ms | " +
            " | ".join([f"{k}={v:.2f}ms" for k, v in phases_ms.items()])
        )
```

#### Phase 3: Non-Streaming API Methods

**File:** [src/ai_service.py](src/ai_service.py)

Modify these methods:
- `_analyze_with_responses_api()` (lines 121-224)
- `_analyze_with_completions_api()` (lines 360-406)
- `_analyze_with_gemini()` (lines 513-563)

Pattern for each method:

```python
def _analyze_with_responses_api(self, image: Image.Image, start_time: datetime) -> dict:
    """Analyze using OpenAI Responses API (GPT-5.x)"""

    # Check if debug latency is enabled
    debug_enabled = (
        self.config.logging.debug_latency and
        logger.isEnabledFor(logging.DEBUG)
    )

    if debug_enabled:
        overall_start_ns = time.perf_counter_ns()

    # ===== PHASE 1: Request Setup =====
    if debug_enabled:
        setup_start_ns = time.perf_counter_ns()

    image_base64 = self._image_to_base64(image)

    api_params = {
        "model": self.config.openai_model,
        "input": [
            {"role": "system", "content": self.prompt_template},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this exam screenshot:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            }
        ],
        **self._get_openai_config_options()
    }

    if debug_enabled:
        setup_ns = time.perf_counter_ns() - setup_start_ns
        network_start_ns = time.perf_counter_ns()

    # ===== PHASE 2: Network Call =====
    try:
        response = self.client.responses.create(**api_params)
    except Exception as e:
        if debug_enabled:
            network_ns = time.perf_counter_ns() - network_start_ns
            logger.debug(
                f"[LATENCY] openai_responses_api | status=ERROR | "
                f"setup={setup_ns / 1_000_000:.2f}ms | "
                f"network={network_ns / 1_000_000:.2f}ms (FAILED)"
            )
        raise

    if debug_enabled:
        network_ns = time.perf_counter_ns() - network_start_ns
        parsing_start_ns = time.perf_counter_ns()

    # ===== PHASE 3: Response Parsing =====
    answer = None
    try:
        # Existing parsing code...
        pass
    except Exception as e:
        logger.error(f"Error extracting answer: {e}")
        raise ValueError(f"Unable to extract answer from API response: {e}")

    if debug_enabled:
        parsing_ns = time.perf_counter_ns() - parsing_start_ns
        total_ns = time.perf_counter_ns() - overall_start_ns

        logger.debug(
            f"[LATENCY] openai_responses_api | "
            f"setup={setup_ns / 1_000_000:.2f}ms | "
            f"network={network_ns / 1_000_000:.2f}ms | "
            f"parsing={parsing_ns / 1_000_000:.2f}ms | "
            f"total={total_ns / 1_000_000:.2f}ms | "
            f"tokens={response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}"
        )

    # ... rest of existing code
```

`★ Insight ─────────────────────────────────────`
**Zero overhead pattern:** The `debug_enabled` check ensures that when disabled, NO timing code runs. The `logger.isEnabledFor(logging.DEBUG)` check adds a second layer of protection - even if the config flag is on, if the logger level is INFO or higher, the timing code is skipped entirely.
`─────────────────────────────────────────────────`

#### Phase 4: Streaming API Methods with TTFT

**File:** [src/ai_service.py](src/ai_service.py)

Modify these methods:
- `_analyze_with_responses_api_streaming()` (lines 226-358)
- `_analyze_with_completions_api_streaming()` (lines 408-487)

Pattern for streaming with TTFT:

```python
def _analyze_with_responses_api_streaming(self, image: Image.Image, start_time: datetime) -> dict:
    """Analyze using OpenAI Responses API with streaming"""

    debug_enabled = (
        self.config.logging.debug_latency and
        logger.isEnabledFor(logging.DEBUG)
    )

    if debug_enabled:
        overall_start_ns = time.perf_counter_ns()
        ttft_ns = None  # Time to first token

    # ===== PHASE 1: Request Setup =====
    if debug_enabled:
        setup_start_ns = time.perf_counter_ns()

    image_base64 = self._image_to_base64(image)
    api_params = {...}

    if debug_enabled:
        setup_ns = time.perf_counter_ns() - setup_start_ns
        network_start_ns = time.perf_counter_ns()

    # ===== PHASE 2: Network + Streaming =====
    stream = self.client.responses.create(**api_params, stream=True)

    total_tokens = 0
    answer_chunks = []

    for event in stream:
        # Track TTFT on first content-bearing event
        if debug_enabled and ttft_ns is None:
            if event.type in [
                'response.reasoning_summary_text.delta',
                'response.output_text.delta'
            ]:
                ttft_ns = time.perf_counter_ns() - network_start_ns

        # Existing streaming logic...

    if debug_enabled:
        network_ns = ttft_ns if ttft_ns else (time.perf_counter_ns() - network_start_ns)
        parsing_start_ns = time.perf_counter_ns()

    # ===== PHASE 3: Response Parsing =====
    answer = ''.join(answer_chunks)

    if debug_enabled:
        parsing_ns = time.perf_counter_ns() - parsing_start_ns
        total_ns = time.perf_counter_ns() - overall_start_ns

        logger.debug(
            f"[LATENCY] openai_responses_api_streaming | "
            f"setup={setup_ns / 1_000_000:.2f}ms | "
            f"ttft={network_ns / 1_000_000:.2f}ms | "
            f"parsing={parsing_ns / 1_000_000:.2f}ms | "
            f"total={total_ns / 1_000_000:.2f}ms | "
            f"tokens={total_tokens}"
        )

    # ... rest of existing code
```

**TTFT Event Types for Responses API:**
- `response.reasoning_summary_text.delta` - First reasoning chunk
- `response.output_text.delta` - First answer chunk

Exclude from TTFT:
- `response.web_search_call.*` - Metadata events
- `response.done.*` - Finalization event

#### Phase 5: Error State Partial Timing

When an API call fails, log completed phases before raising the error:

```python
try:
    response = self.client.responses.create(**api_params)
except Exception as e:
    if debug_enabled:
        network_ns = time.perf_counter_ns() - network_start_ns
        logger.debug(
            f"[LATENCY] openai_responses_api | status=ERROR | "
            f"setup={setup_ns / 1_000_000:.2f}ms | "
            f"network={network_ns / 1_000_000:.2f}ms (FAILED: {type(e).__name__})"
        )
    raise
```

## Acceptance Criteria

### Functional Requirements

- [ ] **Non-streaming methods log 3 phases:** All 3 non-streaming API methods log setup, network, parsing times
- [ ] **Streaming methods log TTFT:** Both streaming methods log time-to-first-token separately
- [ ] **Zero overhead when disabled:** No timing code runs when `debug_latency: false`
- [ ] **Millisecond precision display:** All times displayed in milliseconds (2 decimal places)
- [ ] **Gemini skips base64 tracking:** Gemini setup phase accounts for native PIL image support
- [ ] **Error partial timing:** Failed API calls log completed phases before error

### Non-Functional Requirements

- [ ] **Performance impact <1%:** Benchmark shows <1% difference between enabled/disabled
- [ ] **Works with existing retry logic:** Latency logging works correctly with main.py retry logic
- [ ] **No breaking changes:** Existing log format unchanged at INFO level
- [ ] **All 5 methods instrumented:** Responses API, Completions API, and Gemini (streaming/non-streaming)

### Quality Gates

- [ ] **Unit tests for timing:** Verify phase boundaries are correct
- [ ] **Benchmark comparison:** Run with debug on/off to verify overhead
- [ ] **Log parsing test:** Verify logs are parseable by common tools (grep, jq)
- [ ] **Manual verification:** Trigger screenshot capture and verify log output

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `logging.debug_latency` | bool | `false` | Enable phase breakdown latency logging |
| `logging.latency_precision` | string | `'ms'` | Display precision: `'ns'`, `'ms'`, or `'both'` |
| `logging.latency_format` | string | `'text'` | Log format: `'text'` or `'json'` |

### Usage Examples

**Enable debug latency logging:**
```yaml
# config.yaml
logging:
  level: 'DEBUG'
  debug_latency: true
```

**Sample log output (text format):**
```
2026-01-28 22:45:12,123 - src.ai_service - DEBUG - [LATENCY] openai_responses_api | setup=45.23ms | network=1852.67ms | parsing=12.45ms | total=1910.35ms | tokens=3601
```

**Sample log output (JSON format):**
```json
{
  "timestamp": "2026-01-28T22:45:12.123",
  "level": "DEBUG",
  "logger": "src.ai_service",
  "latency": {
    "operation": "openai_responses_api",
    "phases": {
      "setup_ms": 45.23,
      "network_ms": 1852.67,
      "parsing_ms": 12.45
    },
    "total_ms": 1910.35,
    "tokens": 3601
  }
}
```

## Dependencies & Risks

### Dependencies
- Python 3.10+ (for `time.perf_counter_ns()`)
- Existing `logging` module (no new dependencies)

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Overhead when enabled** | Performance degradation | Guard with `isEnabledFor()` check |
| **TTFT definition ambiguity** | Inconsistent metrics | Document exact event types in code |
| **Gemini base64 difference** | Unfair comparison | Log "image_conversion: 0ms (skipped)" for Gemini |
| **Log file growth** | Disk space | DEBUG logs already increase size; no new impact |

## Implementation Tasks

### Core Implementation

1. [x] **Add config options** - Update [src/config.py](src/config.py) and [config.yaml](config.yaml)
2. [x] **Create PhaseTimer context** - Add latency tracking utility (inline implementation)
3. [x] **Instrument `_analyze_with_responses_api`** - Add 3-phase timing
4. [x] **Instrument `_analyze_with_completions_api`** - Add 3-phase timing
5. [x] **Instrument `_analyze_with_gemini`** - Add 3-phase timing (skip base64)
6. [x] **Instrument `_analyze_with_responses_api_streaming`** - Add TTFT tracking
7. [x] **Instrument `_analyze_with_completions_api_streaming`** - Add TTFT tracking
8. [x] **Add error partial timing** - Log completed phases on failure (included in all methods)
9. [ ] **Add JSON formatter option** - Optional structured logging (skipped - text format only for MVP)

### Testing & Validation

10. [ ] **Create benchmark script** - Compare debug on/off performance
11. [ ] **Manual testing** - Trigger screenshot capture and verify logs
12. [ ] **Log parsing verification** - Test with grep/jq
13. [ ] **Error path testing** - Verify partial timing on failures

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Overhead when disabled** | <0.1% | Benchmark with `debug_latency: false` |
| **Overhead when enabled** | <1% | Benchmark with `debug_latency: true` |
| **Phase accuracy** | ±1ms | Manual verification against known operations |
| **TTFT consistency** | <5% variance | Multiple runs of same screenshot |

## References & Research

### Internal References

- Current timing implementation: [src/ai_service.py:82](src/ai_service.py#L82)
- Logging configuration: [src/output_handler.py:363-394](src/output_handler.py#L363-L394)
- Retry logic: [main.py:29-77](main.py#L29-L77)
- 5 API methods identified:
  - [src/ai_service.py:121-224](src/ai_service.py#L121-L224) - Responses API
  - [src/ai_service.py:226-358](src/ai_service.py#L226-L358) - Responses API streaming
  - [src/ai_service.py:360-406](src/ai_service.py#L360-L406) - Completions API
  - [src/ai_service.py:408-487](src/ai_service.py#L408-L487) - Completions API streaming
  - [src/ai_service.py:513-563](src/ai_service.py#L513-L563) - Gemini

### External References

- Python `time.perf_counter_ns()`: [Python Documentation](https://docs.python.org/3/library/time.html#time.perf_counter_ns)
- OpenAI Python SDK: [/openai/openai-python](https://github.com/openai/openai-python)
- Google GenAI SDK: [/googleapis/python-genai](https://github.com/googleapis/python-genai)
- Python logging best practices: [Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)

### Best Practices Researched

1. **Use `perf_counter_ns()`** - Monotonic clock, nanosecond precision, unaffected by system clock changes
2. **Guard with `isEnabledFor()`** - Zero overhead when logging level is disabled
3. **Structured logging** - Machine-parseable format for analysis tools
4. **TTFT as UX metric** - Time-to-first-token is critical for streaming responsiveness

## Open Questions for Implementation

### Decisions Made (Default Values)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **TTFT definition** | First reasoning OR answer delta | Captures user-perceived responsiveness |
| **Failed API timing** | Log completed phases | Useful for debugging failures |
| **Gemini base64** | Log 0ms with skip message | Fair comparison transparency |
| **Console output** | Phase breakdown in log file only | Avoid console clutter |
| **History JSON** | Only total elapsed time | Minimize file size impact |

### Optional Future Enhancements

- [ ] Add percentile tracking (p50, p95, p99) across multiple calls
- [ ] Add rate limit header logging for OpenAI
- [ ] Add request ID correlation for debugging
- [ ] Add web_search sub-phase timing for Responses API
- [ ] Add retry attempt individual timing

---

**Issue Type:** Enhancement
**Complexity:** Medium (touches 5 API methods, no new files)
**Estimated Effort:** 3-4 hours implementation + 1 hour testing
**Priority:** Low (debug tooling, not user-facing)
