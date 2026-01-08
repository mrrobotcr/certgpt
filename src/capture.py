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
            # Capture the primary monitor
            monitor = self.sct.monitors[1]  # monitors[0] is "all monitors", [1] is primary
            screenshot = self.sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)

            # Save if configured
            saved_path = None
            if self.config.save_screenshots:
                saved_path = self._save_screenshot(img)

            logger.info(f"Screenshot captured: {img.size}")
            return img, saved_path

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            raise

    def _save_screenshot(self, img: Image.Image) -> str:
        """Save screenshot to disk with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"exam_{timestamp}.{self.config.screenshot_format}"
        filepath = self.config.screenshot_dir / filename

        img.save(filepath, self.config.screenshot_format.upper())
        logger.debug(f"Screenshot saved to: {filepath}")
        return str(filepath)

    def image_to_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL Image to bytes for API transmission"""
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()


class KeyboardListener:
    """
    Keyboard listener using pynput (MacOS-optimized)
    Supports configurable hotkeys
    """

    def __init__(self, on_trigger: Callable):
        """
        Initialize keyboard listener

        Args:
            on_trigger: Callback function to call when trigger key is pressed
        """
        self.config = get_config()
        self.on_trigger = on_trigger
        self.listener: Optional[keyboard.Listener] = None
        self.running = False

        # Parse trigger key configuration
        self.trigger_key = self._parse_trigger_key(self.config.trigger_key)
        logger.info(f"Keyboard listener initialized with trigger: {self.config.trigger_key}")

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
        """Internal callback for key press events"""
        try:
            # Debug: log all key presses
            key_info = f"char='{key.char}'" if hasattr(key, 'char') else f"special={key}"
            logger.debug(f"Key pressed: {key_info}, looking for: '{self.trigger_key}'")

            # Handle regular character keys
            if hasattr(key, 'char') and key.char is not None:
                if key.char == self.trigger_key:
                    logger.info(f"✓ Trigger key matched: {self.trigger_key}")
                    self.on_trigger()
                    return

        except AttributeError:
            pass

        # Handle special keys (F1-F12, etc.)
        try:
            key_name = str(key).replace('Key.', '')
            if key_name == self.trigger_key:
                logger.info(f"✓ Trigger key matched (special): {self.trigger_key}")
                self.on_trigger()
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
    """

    def __init__(self, on_screenshot_callback: Callable[[Image.Image, Optional[str]], None]):
        """
        Initialize capture manager

        Args:
            on_screenshot_callback: Function to call with (image, saved_path) when screenshot is taken
        """
        self.config = get_config()
        self.screen_capture = ScreenCapture()
        self.keyboard_listener = KeyboardListener(on_trigger=self._handle_trigger)
        self.on_screenshot_callback = on_screenshot_callback

        # Initialize mouse listener if enabled
        self.mouse_listener: Optional[MouseListener] = None
        if self.config.enable_middle_button:
            self.mouse_listener = MouseListener(on_trigger=self._handle_trigger)
            logger.info("CaptureManager initialized with keyboard + mouse triggers")
        else:
            logger.info("CaptureManager initialized with keyboard trigger only")

    def _handle_trigger(self):
        """Internal handler for trigger key/button press"""
        try:
            logger.info("Trigger activated - capturing screenshot")
            img, saved_path = self.screen_capture.capture_fullscreen()
            self.on_screenshot_callback(img, saved_path)

        except Exception as e:
            logger.error(f"Error handling trigger: {e}")

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
