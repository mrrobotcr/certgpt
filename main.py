#!/usr/bin/env python3
"""
ExamsGPT - AI-powered exam assistant for Microsoft Azure certifications

Press configured key (default: '\') to capture screenshot and get AI analysis
"""

import sys
import signal
import logging
import time
from typing import Optional
from PIL import Image

from src.config import init_config
from src.capture import CaptureManager
from src.ai_service import AIService
from src.output_handler import OutputHandler, Logger


logger = logging.getLogger(__name__)


# Retry configuration for transient failures
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def retry_on_transient_error(func, *args, **kwargs):
    """
    Retry a function on transient errors with exponential backoff

    Args:
        func: Function to retry
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        The result of func(*args, **kwargs)

    Raises:
        Exception: If all retries are exhausted
    """
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            error_msg = str(e).lower()

            # Check if this is a transient error
            transient_keywords = [
                'connection', 'timeout', 'network', 'temporary', 'unavailable',
                'rate limit', '429', '503', '502', '500', 'connection reset',
                'broken pipe', 'timed out'
            ]

            is_transient = any(keyword in error_msg for keyword in transient_keywords)

            if not is_transient:
                # Not a transient error, don't retry
                logger.error(f"Non-transient error: {e}")
                raise

            # Transient error - retry with backoff
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Transient error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Max retries reached for transient error: {e}")

    # All retries exhausted
    raise last_exception


class ExamsGPT:
    """Main application class"""

    def __init__(self):
        # Initialize configuration
        self.config = init_config()

        # Setup logging
        Logger.setup_logging(self.config)

        logger.info("=" * 70)
        logger.info("ExamsGPT Starting...")
        logger.info(f"Mode: {self.config.app_mode}")
        logger.info(f"Model: {self.config.openai_model}")
        logger.info(f"Trigger Key: {self.config.trigger_key}")
        logger.info(f"Middle Mouse Button: {'enabled' if self.config.enable_middle_button else 'disabled'}")
        logger.info("=" * 70)

        # Initialize services
        self.ai_service = AIService()
        self.output_handler = OutputHandler()
        self.capture_manager = CaptureManager(
            on_screenshot_callback=self.handle_screenshot
        )

        # Flag for graceful shutdown
        self.running = False

    def handle_screenshot(self, image: Image.Image, screenshot_path: Optional[str]):
        """
        Callback when screenshot is captured

        Args:
            image: PIL Image of the screenshot
            screenshot_path: Path where screenshot was saved (if enabled)
        """
        try:
            logger.info("Processing screenshot...")

            # Notify frontend that processing has started
            self.output_handler.send_processing()

            # Analyze with AI
            result = self.ai_service.analyze_exam_screenshot(image)

            # Handle output
            self.output_handler.handle_result(result, screenshot_path)

        except Exception as e:
            logger.error(f"Error processing screenshot: {e}")

    def start(self):
        """Start the application"""
        try:
            # Test OpenAI connection with retry logic
            print("\nTesting OpenAI connection...")
            try:
                retry_on_transient_error(self.ai_service.test_connection)
                print("✓ OpenAI connection successful\n")
            except Exception as e:
                print(f"ERROR: Failed to connect to OpenAI API after {MAX_RETRIES} attempts")
                print(f"Details: {e}")
                print("\nPlease check your OPENAI_API_KEY in .env file")
                print("If this is a transient network error, the service will retry automatically.")
                sys.exit(1)

            # Start capture manager
            self.capture_manager.start()
            self.running = True

            # Print instructions
            print("=" * 70)
            print("ExamsGPT is running!")
            print("=" * 70)
            print(f"Press '{self.config.trigger_key}' to capture and analyze exam question")
            if self.config.enable_middle_button:
                print("Or click the middle mouse button (scroll wheel)")
            print("Press Ctrl+C to stop")
            print("=" * 70)
            print()

            # Keep running until interrupted
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            # Block main thread
            signal.pause()

        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            self.stop()

    def stop(self):
        """Stop the application gracefully"""
        if self.running:
            print("\n\nStopping ExamsGPT...")
            self.capture_manager.stop()
            self.running = False
            logger.info("ExamsGPT stopped")
            print("Goodbye!\n")

    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        self.stop()
        sys.exit(0)


def main():
    """Entry point"""
    try:
        # Check if .env exists
        import os
        if not os.path.exists('.env'):
            print("ERROR: .env file not found!")
            print("\nPlease create a .env file based on .env.example:")
            print("  cp .env.example .env")
            print("\nThen add your OpenAI API key to .env")
            sys.exit(1)

        # Run application with initialization retry
        max_init_retries = 3
        init_delay = 2

        for attempt in range(max_init_retries):
            try:
                app = ExamsGPT()
                app.start()
                break  # If start() succeeds, exit the retry loop
            except Exception as e:
                error_msg = str(e).lower()

                # Check if this is a potentially transient error
                transient_keywords = [
                    'connection', 'timeout', 'network', 'temporary', 'unavailable',
                    'already in use', 'address already in use'
                ]
                is_transient = any(keyword in error_msg for keyword in transient_keywords)

                if is_transient and attempt < max_init_retries - 1:
                    print(f"\nInitialization error (attempt {attempt + 1}/{max_init_retries}): {e}")
                    print(f"Retrying in {init_delay}s...")
                    time.sleep(init_delay)
                    init_delay *= 2  # Exponential backoff
                else:
                    # Either not transient or out of retries
                    raise

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
