"""
Screenshot and keyboard handling for ExamsGPT
Optimized for MacOS with cross-platform support
"""

import mss
import logging
from datetime import datetime
from pathlib import Path
from PIL import Image
from pynput import keyboard, mouse
from typing import Callable, Optional
from io import BytesIO

from .config import get_config


logger = logging.getLogger(__name__)


class ScreenCapture:
    """Handles screenshot capture using mss (optimized for MacOS/Retina displays)"""

    def __init__(self):
        self.config = get_config()
        self.sct = mss.mss()

    def capture_fullscreen(self) -> tuple[Image.Image, Optional[str]]:
        """
        Capture full screen and return PIL Image + optional saved path

        Returns:
            tuple: (PIL Image object, saved file path or None)
        """
        try:
            logger.info(f"[ScreenCapture.capture_fullscreen] >>> START: Getting monitor info...")
            # Capture the primary monitor
            monitor = self.sct.monitors[1]  # monitors[0] is "all monitors", [1] is primary
            logger.info(f"[ScreenCapture.capture_fullscreen] Monitor: {monitor}")
            logger.info(f"[ScreenCapture.capture_fullscreen] Calling sct.grab()...")
            screenshot = self.sct.grab(monitor)
            logger.info(f"[ScreenCapture.capture_fullscreen] ✓ grab() returned, size: {screenshot.size}")

            # Convert to PIL Image
            logger.info(f"[ScreenCapture.capture_fullscreen] Converting to PIL Image...")
            img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
            logger.info(f"[ScreenCapture.capture_fullscreen] ✓ PIL Image created: {img.size}")

            # Save if configured
            saved_path = None
            if self.config.save_screenshots:
                logger.info(f"[ScreenCapture.capture_fullscreen] Saving screenshot...")
                saved_path = self._save_screenshot(img)
                logger.info(f"[ScreenCapture.capture_fullscreen] ✓ Saved to: {saved_path}")

            logger.info(f"[ScreenCapture.capture_fullscreen] >>> DONE: Screenshot captured: {img.size}")
            return img, saved_path

        except Exception as e:
            logger.error(f"[ScreenCapture.capture_fullscreen] ERROR: Failed to capture: {e}", exc_info=True)
            raise

    def _save_screenshot(self, img: Image.Image) -> str:
        """Save screenshot to disk with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # Map format to file extension
        ext_map = {'jpeg': 'jpg', 'webp': 'webp', 'png': 'png'}
        ext = ext_map.get(self.config.screenshot_format, 'png')
        filename = f"exam_{timestamp}.{ext}"
        filepath = self.config.screenshot_dir / filename

        # Apply format-specific settings
        if self.config.screenshot_format == 'jpeg':
            # Convert to RGB (JPEG doesn't support transparency)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Optional resize for large screens
            if self.config.screenshot_max_width or self.config.screenshot_max_height:
                img = self._resize_if_needed(img)
            img.save(filepath, format='JPEG', quality=self.config.screenshot_jpeg_quality)
        elif self.config.screenshot_format == 'webp':
            # Convert to RGB (WebP doesn't support transparency in basic mode)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Optional resize for large screens
            if self.config.screenshot_max_width or self.config.screenshot_max_height:
                img = self._resize_if_needed(img)
            img.save(filepath, format='WEBP', quality=self.config.screenshot_webp_quality, method=6)
        else:
            img.save(filepath, format='PNG')

        logger.debug(f"Screenshot saved to: {filepath}")
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

    def image_to_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL Image to bytes for API transmission"""
        buffer = BytesIO()

        # Determine format based on configuration
        if self.config.screenshot_format == 'jpeg':
            save_format = 'JPEG'
            quality = self.config.screenshot_jpeg_quality
        elif self.config.screenshot_format == 'webp':
            save_format = 'WEBP'
            quality = self.config.screenshot_webp_quality
        else:
            save_format = 'PNG'
            quality = None

        if save_format == 'JPEG':
            # Convert to RGB if necessary (JPEG doesn't support transparency)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(buffer, format='JPEG', quality=quality)
        elif save_format == 'WEBP':
            # Convert to RGB if necessary (WebP doesn't support transparency in basic mode)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(buffer, format='WEBP', quality=quality, method=6)
        else:
            img.save(buffer, format='PNG')

        return buffer.getvalue()


class KeyboardListener:
    """
    Keyboard listener using pynput (MacOS-optimized)
    Supports multiple trigger keys with a single listener to avoid TIS/TSM crashes
    """

    def __init__(self, on_trigger: Callable[[str], None], trigger_keys: list[str]):
        """
        Initialize keyboard listener

        Args:
            on_trigger: Callback function that receives the key that was pressed
            trigger_keys: List of trigger keys to listen for
        """
        self.config = get_config()
        self.on_trigger = on_trigger
        self.listener: Optional[keyboard.Listener] = None
        self.running = False

        # Parse all trigger keys
        self.trigger_keys = [self._parse_trigger_key(k) for k in trigger_keys]
        logger.info(f"Keyboard listener initialized with triggers: {self.trigger_keys}")

    def _parse_trigger_key(self, key_string: str) -> str:
        """
        Parse trigger key string into normalized format

        Examples:
            '\\' -> '\\'
            'f12' -> 'f12'
            'ctrl+\\' -> combination handling
        """
        # For now, support single keys (combinations can be added later)
        return key_string.strip()

    def _on_press(self, key):
        """Internal callback for key press events - checks against multiple trigger keys"""
        try:
            # Try to match against regular character keys
            if hasattr(key, 'char') and key.char is not None:
                if key.char in self.trigger_keys:
                    logger.info(f"[KeyboardListener._on_press] ✓ Key '{key.char}' matched, calling on_trigger...")
                    self.on_trigger(key.char)
                    return

            # Try to match against special keys (F1-F12, etc.)
            key_name = str(key).replace('Key.', '')
            if key_name in self.trigger_keys:
                logger.info(f"[KeyboardListener._on_press] ✓ Special key '{key_name}' matched, calling on_trigger...")
                self.on_trigger(key_name)
                return

        except Exception as e:
            logger.error(f"Error in key handler: {e}")

    def start(self):
        """Start listening for keyboard events"""
        if self.running:
            logger.warning("Keyboard listener already running")
            return

        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()
        self.running = True
        logger.info("Keyboard listener started")

    def stop(self):
        """Stop listening for keyboard events"""
        if self.listener and self.running:
            self.listener.stop()
            self.running = False
            logger.info("Keyboard listener stopped")


class MouseListener:
    """
    Mouse listener using pynput
    Triggers on middle button (scroll wheel) click
    """

    def __init__(self, on_trigger: Callable):
        """
        Initialize mouse listener

        Args:
            on_trigger: Callback function to call when middle button is clicked
        """
        self.config = get_config()
        self.on_trigger = on_trigger
        self.listener: Optional[mouse.Listener] = None
        self.running = False
        logger.info("Mouse listener initialized (middle button trigger)")

    def _on_click(self, x, y, button, pressed):
        """Internal callback for mouse click events"""
        try:
            if button == mouse.Button.middle and pressed:
                logger.info("✓ Middle mouse button clicked - triggering capture")
                self.on_trigger()
        except Exception as e:
            logger.error(f"Error in mouse handler: {e}")

    def start(self):
        """Start listening for mouse events"""
        if self.running:
            logger.warning("Mouse listener already running")
            return

        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()
        self.running = True
        logger.info("Mouse listener started")

    def stop(self):
        """Stop listening for mouse events"""
        if self.listener and self.running:
            self.listener.stop()
            self.running = False
            logger.info("Mouse listener stopped")


class CaptureManager:
    """
    Main manager coordinating screenshot capture and input events (keyboard + mouse)
    Supports single-shot and queue-based workflows

    IMPORTANT: Uses a SINGLE keyboard listener to avoid macOS TIS/TSM API crash
    """

    def __init__(self,
                 on_screenshot_callback: Callable[[Image.Image, Optional[str]], None],
                 on_queue_add_callback: Callable[[Image.Image, Optional[str]], None] = None,
                 on_queue_send_callback: Callable[[], None] = None):
        """
        Initialize capture manager

        Args:
            on_screenshot_callback: Function to call with (image, saved_path) when screenshot is taken
            on_queue_add_callback: Optional function to call when queue key is pressed
            on_queue_send_callback: Optional function to call when send key is pressed
        """
        self.config = get_config()
        self.screen_capture = ScreenCapture()
        self.on_screenshot_callback = on_screenshot_callback

        # Queue callbacks (optional)
        self.on_queue_add_callback = on_queue_add_callback
        self.on_queue_send_callback = on_queue_send_callback

        # Collect all trigger keys and their handlers
        # Format: {trigger_key: callback_function}
        self.key_handlers: dict[str, Callable] = {}

        # Primary trigger key
        self.key_handlers[self.config.trigger_key] = self._handle_trigger

        # Queue keys (if configured)
        if self.config.queue_key and on_queue_add_callback:
            self.key_handlers[self.config.queue_key] = self._handle_queue_add
            logger.info(f"Queue key '{self.config.queue_key}' registered")

        if self.config.send_key and on_queue_send_callback:
            self.key_handlers[self.config.send_key] = self._handle_queue_send
            logger.info(f"Send key '{self.config.send_key}' registered")

        # Create SINGLE keyboard listener with all keys
        self.keyboard_listener = KeyboardListener(
            on_trigger=self._handle_any_key,
            trigger_keys=list(self.key_handlers.keys())
        )
        logger.info(f"CaptureManager initialized with {len(self.key_handlers)} key(s): {list(self.key_handlers.keys())}")

        # Initialize mouse listener if enabled
        self.mouse_listener: Optional[MouseListener] = None
        if self.config.enable_middle_button:
            self.mouse_listener = MouseListener(on_trigger=self._handle_trigger)
            logger.info("Mouse listener also enabled")

    def _handle_any_key(self, key: str):
        """
        Unified handler for all registered keys - called by single listener
        Routes to appropriate handler based on which key was pressed
        """
        if key in self.key_handlers:
            logger.info(f"[CaptureManager] Key '{key}' pressed, routing to handler")
            handler = self.key_handlers[key]
            handler()
        else:
            logger.warning(f"[CaptureManager] Unregistered key pressed: '{key}'")

    def _handle_trigger(self):
        """Internal handler for trigger key/button press"""
        try:
            logger.info(f"[CaptureManager._handle_trigger] >>> START: Trigger activated")
            logger.info(f"[CaptureManager._handle_trigger] Calling capture_fullscreen()...")
            img, saved_path = self.screen_capture.capture_fullscreen()
            logger.info(f"[CaptureManager._handle_trigger] ✓ capture_fullscreen() returned: img={img.size}, path={saved_path}")
            logger.info(f"[CaptureManager._handle_trigger] Calling on_screenshot_callback()...")
            self.on_screenshot_callback(img, saved_path)
            logger.info(f"[CaptureManager._handle_trigger] ✓ on_screenshot_callback() returned")
            logger.info(f"[CaptureManager._handle_trigger] >>> DONE: Trigger completed")

        except Exception as e:
            logger.error(f"[CaptureManager._handle_trigger] ERROR: {e}", exc_info=True)

    def _handle_queue_add(self):
        """Handle queue key press - add screenshot to queue"""
        try:
            logger.info("Queue key activated - capturing screenshot for queue")
            img, saved_path = self.screen_capture.capture_fullscreen()
            # Call the queue add callback with the screenshot
            # The callback signature is: Callable[[Image.Image, Optional[str]], None]
            if self.on_queue_add_callback:
                self.on_queue_add_callback(img, saved_path)
        except Exception as e:
            logger.error(f"Error handling queue add: {e}")

    def _handle_queue_send(self):
        """Handle send key press - send queue for analysis"""
        try:
            logger.info("Send key activated - processing queue")
            if self.on_queue_send_callback:
                self.on_queue_send_callback()
        except Exception as e:
            logger.error(f"Error handling queue send: {e}")

    def start(self):
        """Start the capture manager (keyboard + mouse listeners)"""
        logger.info("Starting CaptureManager...")
        self.keyboard_listener.start()
        if self.mouse_listener:
            self.mouse_listener.start()

    def stop(self):
        """Stop the capture manager"""
        logger.info("Stopping CaptureManager...")
        self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()

    def is_running(self) -> bool:
        """Check if capture manager is running"""
        return self.keyboard_listener.running
