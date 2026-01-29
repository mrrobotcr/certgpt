# feat: Optimize screenshot size with JPEG compression

## Overview

Optimize screenshot file size by converting from PNG to JPEG format with compression, reducing API request latency while maintaining text readability for AI analysis.

`★ Insight ─────────────────────────────────────`
**Why this matters:** Current PNG screenshots are ~1MB each, causing slow API requests. JPEG with quality 75-85 can reduce size by ~90% while maintaining text clarity for vision APIs.
`─────────────────────────────────────────────────`

## Problem Statement

**Current State:**
- Screenshots saved as PNG format (~1MB per file)
- No compression or optimization applied
- Large base64 payloads sent to OpenAI APIs
- Slow API request times due to payload size

**Impact:**
- Slower analysis response times
- Higher API costs (larger payloads)
- More disk space usage for saved screenshots

## Proposed Solution

Convert screenshots from PNG to JPEG format with configurable quality settings. Focus on text readability while achieving ~90% size reduction.

### Key Changes

1. **Format change:** PNG → JPEG
2. **Quality setting:** 75-85 (balanced for text readability)
3. **New config options:** `screenshot.format`, `screenshot.jpeg_quality`
4. **Update image processing:** `_save_screenshot()` and `_image_to_base64()`

## Technical Approach

### Configuration

**File:** [config.yaml](config.yaml)

```yaml
screenshot:
  save_screenshots: true
  directory: 'screenshots'
  format: 'jpeg'              # NEW: 'png' | 'jpeg'
  jpeg_quality: 80            # NEW: 1-100, 75-85 recommended for text
  max_width: 1920             # NEW: optional, resize large screens
  max_height: 1080            # NEW: optional, resize large screens
```

**File:** [src/config.py](src/config.py)

```python
# Screenshot Configuration
self.save_screenshots = self.yaml_config['screenshot']['save_screenshots']
self.screenshot_dir = self.root_dir / self.yaml_config['screenshot']['directory']
self.screenshot_format = self.yaml_config['screenshot']['format']
self.screenshot_jpeg_quality = self.yaml_config['screenshot'].get('jpeg_quality', 80)
self.screenshot_max_width = self.yaml_config['screenshot'].get('max_width', None)
self.screenshot_max_height = self.yaml_config['screenshot'].get('max_height', None)
```

### Implementation

**File:** [src/capture.py](src/capture.py)

Modify `_save_screenshot()` to use JPEG format:

```python
def _save_screenshot(self, img: Image.Image) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ext = 'jpg' if self.config.screenshot_format == 'jpeg' else 'png'
    filename = f"exam_{timestamp}.{ext}"
    filepath = self.config.screenshot_dir / filename

    # Apply format-specific settings
    if self.config.screenshot_format == 'jpeg':
        # Convert RGB (JPEG doesn't support transparency)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        # Optional resize for large screens
        if (self.config.screenshot_max_width or self.config.screenshot_max_height):
            img = self._resize_if_needed(img)
        img.save(filepath, format='JPEG', quality=self.config.screenshot_jpeg_quality)
    else:
        img.save(filepath, format='PNG')

    return str(filepath)

def _resize_if_needed(self, img: Image.Image) -> Image.Image:
    """Resize image if exceeds max dimensions while maintaining aspect ratio"""
    max_w = self.config.screenshot_max_width or img.width
    max_h = self.config.screenshot_max_height or img.height

    if img.width <= max_w and img.height <= max_h:
        return img

    # Calculate maintaining aspect ratio
    ratio = min(max_w / img.width, max_h / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    return img.resize(new_size, Image.LANCZOS)  # High-quality resampling
```

**File:** [src/ai_service.py](src/ai_service.py)

Modify `_image_to_base64()` to use JPEG format for OpenAI:

```python
def _image_to_base64(self, image: Image.Image) -> str:
    buffer = BytesIO()

    # Convert to RGB if necessary (JPEG doesn't support RGBA)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # Use JPEG format for smaller payloads if configured
    save_format = 'JPEG' if self.config.screenshot_format == 'jpeg' else 'PNG'

    if save_format == 'JPEG':
        image.save(buffer, format='JPEG', quality=self.config.screenshot_jpeg_quality)
    else:
        image.save(buffer, format='PNG')

    image_bytes = buffer.getvalue()
    return base64.b64encode(image_bytes).decode('utf-8')
```

## Acceptance Criteria

- [ ] **JPEG format enabled:** Screenshots saved as .jpg files
- [ ] **Configurable quality:** `jpeg_quality` setting in config.yaml
- [ ] **Size reduction:** ~90% smaller files (1MB → ~100KB)
- [ ] **Text readability:** Text remains clear for AI analysis
- [ ] **Optional resize:** `max_width`/`max_height` configuration works
- [ ] **PNG fallback:** Can still use PNG if needed
- [ ] **Works for both:** Saved files AND base64 payloads

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `format` | string | `'jpeg'` | Image format: `'png'` or `'jpeg'` |
| `jpeg_quality` | integer | `80` | JPEG quality: 1-100 (75-85 for text) |
| `max_width` | integer | `1920` | Max width, `null` to disable resize |
| `max_height` | integer | `1080` | Max height, `null` to disable resize |

### Usage Examples

**Balanced quality (recommended):**
```yaml
screenshot:
  format: 'jpeg'
  jpeg_quality: 80
```

**High quality (larger files):**
```yaml
screenshot:
  format: 'jpeg'
  jpeg_quality: 90
```

**Maximum compression (smaller files):**
```yaml
screenshot:
  format: 'jpeg'
  jpeg_quality: 75
```

**Original PNG (no compression):**
```yaml
screenshot:
  format: 'png'
```

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| **File size** | ~1MB | ~100KB | <150KB |
| **API latency** | ~5s | ~2s | <3s |
| **Text accuracy** | 100% | >95% | >95% |

## Dependencies & Risks

### Dependencies
- Pillow (PIL) - already installed
- No new dependencies required

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Text quality loss** | AI misreads text | Keep quality ≥75, test with exam screenshots |
| **No transparency** | UI elements with transparency | JPEG doesn't support alpha - convert to RGB |
| **Resize artifacts** | Blurry text on resized images | Use LANCZOS resampling, test max dimensions |

## Implementation Tasks

1. [x] **Add config options** - Update config.yaml and src/config.py
2. [x] **Modify `_save_screenshot()`** - Add JPEG support with quality
3. [x] **Add `_resize_if_needed()`** - Optional resize for large screens
4. [x] **Modify `_image_to_base64()`** - Use JPEG for base64 encoding
5. [x] **Update `image_to_bytes()`** - Add JPEG format support
6. [ ] **Testing** - Verify text readability with actual exam screenshots

## References

### Internal References

- Screenshot capture: [src/capture.py:28-63](src/capture.py#L28-L63)
- Base64 conversion: [src/ai_service.py:792-809](src/ai_service.py#L792-L809)
- Current config: [config.yaml:20-27](config.yaml#L20-L27)
- Config loading: [src/config.py:78-80](src/config.py#L78-L80)

### External References

- Pillow JPEG documentation: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg
- Image.LANCZOS resampling: https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize
- OpenAI Vision API: Images up to 20MB, supports PNG and JPEG

---

**Issue Type:** Enhancement
**Complexity:** Low (simple format conversion)
**Estimated Effort:** 1-2 hours implementation + 30 min testing
**Priority:** Medium (performance improvement)
