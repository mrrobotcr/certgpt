#!/usr/bin/env python3
"""
ExamsGPT - AI-powered exam assistant for Microsoft Azure certifications

Press configured key (default: '\') to capture screenshot and get AI analysis
"""

import sys
import signal
import logging
from typing import Optional
from PIL import Image

from src.config import init_config
from src.capture import CaptureManager
from src.ai_service import AIService
from src.output_handler import OutputHandler, Logger


logger = logging.getLogger(__name__)


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
            # Test OpenAI connection
            print("\nTesting OpenAI connection...")
            if not self.ai_service.test_connection():
                print("ERROR: Failed to connect to OpenAI API")
                print("Please check your OPENAI_API_KEY in .env file")
                return

            print("✓ OpenAI connection successful\n")

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

        # Run application
        app = ExamsGPT()
        app.start()

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
