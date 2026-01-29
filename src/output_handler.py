"""
Output handling for ExamsGPT
Extensible architecture supporting console, socket.io, and webhook outputs
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol
from abc import ABC, abstractmethod

from .config import get_config


logger = logging.getLogger(__name__)


class OutputStrategy(ABC):
    """Abstract base class for output strategies"""

    @abstractmethod
    def send(self, result: dict, screenshot_path: Optional[str] = None):
        """Send the analysis result"""
        pass

    def send_processing(self):
        """Send processing status (optional, not all strategies support this)"""
        pass


class ConsoleOutput(OutputStrategy):
    """Output to console (for development)"""

    def send_processing(self):
        """Print processing status to console"""
        print("\n⏳ Processing screenshot with AI...")

    def send(self, result: dict, screenshot_path: Optional[str] = None):
        """Print result to console with nice formatting"""
        separator = "=" * 70
        print(f"\n{separator}")
        print(f"[{result['timestamp']}] EXAM ANSWER")
        print(separator)

        if result['success']:
            print(f"\n{result['answer']}\n")
            print(f"Model: {result['model']}")
            print(f"Time: {result['elapsed_seconds']:.2f}s")
            if result.get('tokens_used'):
                print(f"Tokens: {result['tokens_used']}")
            if screenshot_path:
                print(f"Screenshot: {screenshot_path}")
        else:
            print(f"\nERROR: {result.get('error', 'Unknown error')}\n")

        print(separator + "\n")


class SocketIOOutput(OutputStrategy):
    """
    Output to Socket.IO server (for production)
    TODO: Implement when needed
    """

    def __init__(self, url: str, namespace: str):
        self.url = url
        self.namespace = namespace
        logger.warning("SocketIOOutput not yet implemented")
        # Future: import socketio and setup client

    def send(self, result: dict, screenshot_path: Optional[str] = None):
        """Send result via Socket.IO"""
        logger.warning("SocketIOOutput.send() called but not implemented yet")
        # Future implementation:
        # self.socketio.emit('exam_answer', result, namespace=self.namespace)


class WebhookOutput(OutputStrategy):
    """
    Output to webhook endpoint (for production)
    Sends POST request to Nuxt app with retry logic
    """

    MAX_RETRIES = 3
    INITIAL_BACKOFF = 0.5  # seconds

    def __init__(self, url: str):
        self.url = url
        logger.info(f"WebhookOutput initialized with URL: {url}")

    def _send_with_retry(self, payload: dict, description: str) -> bool:
        """
        Send payload to webhook with exponential backoff retry.
        Returns True if successful, False otherwise.
        """
        import requests
        import time

        backoff = self.INITIAL_BACKOFF

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(f"[Attempt {attempt}/{self.MAX_RETRIES}] Sending {description} to webhook")
                response = requests.post(
                    self.url,
                    json=payload,
                    timeout=10  # Increased timeout
                )

                if response.status_code == 200:
                    logger.info(f"✓ {description} delivered successfully on attempt {attempt}")
                    return True
                else:
                    logger.warning(f"Webhook returned status {response.status_code}: {response.text}")

            except requests.exceptions.Timeout:
                logger.warning(f"Webhook timeout on attempt {attempt}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error on attempt {attempt}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt}: {e}")

            # Wait before retry (except on last attempt)
            if attempt < self.MAX_RETRIES:
                logger.info(f"Retrying in {backoff:.1f}s...")
                time.sleep(backoff)
                backoff *= 2  # Exponential backoff

        logger.error(f"✗ Failed to deliver {description} after {self.MAX_RETRIES} attempts")
        return False

    def send_processing(self):
        """Send processing status to frontend via webhook"""
        try:
            payload = {
                'type': 'processing',
                'timestamp': datetime.now().isoformat()
            }
            self._send_with_retry(payload, "processing status")
        except ImportError:
            logger.error("requests library not installed. Run: pip install requests")
        except Exception as e:
            logger.error(f"Error preparing processing status: {e}")

    def send(self, result: dict, screenshot_path: Optional[str] = None):
        """Send result via HTTP POST to webhook with retry"""
        try:
            # Prepare payload
            payload = {
                'type': 'answer',
                'answer': result['answer'],
                'timestamp': result['timestamp'],
                'model': result.get('model'),
                'elapsed_seconds': result.get('elapsed_seconds'),
                'tokens_used': result.get('tokens_used')
            }

            self._send_with_retry(payload, "answer")

        except ImportError:
            logger.error("requests library not installed. Run: pip install requests")
        except Exception as e:
            logger.error(f"Error preparing answer payload: {e}")


class StreamingWebhookOutput(WebhookOutput):
    """
    Webhook output with streaming support
    Sends chunks as they arrive from AI service
    """

    def __init__(self, url: str):
        super().__init__(url)
        self.message_id = None

    def send_processing(self):
        """Send processing status to frontend via webhook (with streaming flag)"""
        try:
            # Generate message ID for this streaming session
            if self.message_id is None:
                import time
                self.message_id = f"{int(time.time() * 1000)}-{id(self)}"

            payload = {
                'type': 'processing',
                'timestamp': datetime.now().isoformat(),
                'streaming': True,  # Indicate streaming mode
                'message_id': self.message_id
            }
            self._send_with_retry(payload, "processing status")
        except Exception as e:
            logger.error(f"Error preparing processing status: {e}")

    def send_streaming_chunk(self, chunk: str, content_type: str = 'answer'):
        """
        Send a streaming chunk to the frontend

        Args:
            chunk: Content chunk from AI service
            content_type: Type of content ('reasoning', 'answer', 'error')
        """
        logger.info(f"[send_streaming_chunk] Called with {len(chunk)} chars, type: {content_type}")
        try:
            import requests

            # Ensure we have a message ID
            if self.message_id is None:
                import time
                self.message_id = f"{int(time.time() * 1000)}-{id(self)}"
                logger.info(f"[send_streaming_chunk] Generated message_id: {self.message_id}")

            payload = {
                'type': 'streaming_chunk',
                'content': chunk,
                'content_type': content_type,
                'message_id': self.message_id,
                'timestamp': datetime.now().isoformat()
            }

            # Send without retry for streaming chunks (latency critical)
            try:
                response = requests.post(
                    self.url,
                    json=payload,
                    timeout=5  # Short timeout for chunks
                )
                if response.status_code == 200:
                    logger.info(f"[Webhook Streaming] Chunk sent: {len(chunk)} chars, type: {content_type}")
                else:
                    logger.warning(f"Streaming chunk failed: {response.status_code}")
            except requests.exceptions.RequestException as e:
                # Don't retry streaming chunks to avoid backlog
                logger.warning(f"Failed to send streaming chunk: {e}")

        except ImportError:
            logger.error("requests library not installed")
        except Exception as e:
            logger.error(f"Error sending streaming chunk: {e}")

    def send(self, result: dict, screenshot_path: Optional[str] = None):
        """Send final result via streaming completion event"""
        try:
            import requests

            payload = {
                'type': 'streaming_complete',
                'answer': result['answer'],
                'timestamp': result['timestamp'],
                'model': result.get('model'),
                'elapsed_seconds': result.get('elapsed_seconds'),
                'tokens_used': result.get('tokens_used'),
                'message_id': self.message_id,
                'success': result['success']
            }

            if not result['success']:
                payload['error'] = result.get('error')

            # Send with retry for final result
            self._send_with_retry(payload, "streaming completion")

            # Reset message ID for next request
            self.message_id = None

        except ImportError:
            logger.error("requests library not installed")
        except Exception as e:
            logger.error(f"Error preparing streaming completion: {e}")


class OutputHandler:
    """
    Main output handler that coordinates different output strategies
    and handles logging/history
    """

    def __init__(self):
        self.config = get_config()
        self.strategy = self._create_strategy()
        logger.info(f"OutputHandler initialized with mode: {self.config.app_mode}, streaming_enabled: {self.config.streaming_enabled}")
        logger.info(f"Strategy type: {type(self.strategy).__name__}")

    def _create_strategy(self) -> OutputStrategy:
        """Create appropriate output strategy based on configuration"""
        mode = self.config.app_mode.lower()

        if mode == "dev":
            return ConsoleOutput()
        elif mode == "socketio":
            return SocketIOOutput(
                url=self.config.socketio_url,
                namespace=self.config.socketio_namespace
            )
        elif mode == "webhook":
            # Use streaming output if enabled
            if self.config.streaming_enabled:
                return StreamingWebhookOutput(url=self.config.webhook_url)
            else:
                return WebhookOutput(url=self.config.webhook_url)
        else:
            logger.warning(f"Unknown mode '{mode}', defaulting to console")
            return ConsoleOutput()

    def send_processing(self):
        """
        Send processing status to indicate AI analysis has started.
        Called before the AI service is invoked.
        """
        try:
            self.strategy.send_processing()
        except Exception as e:
            logger.error(f"Error sending processing status: {e}")

    def get_streaming_callback(self):
        """
        Get streaming callback if strategy supports it
        Returns callback function or None
        """
        if hasattr(self.strategy, 'send_streaming_chunk'):
            return self.strategy.send_streaming_chunk
        return None

    def handle_result(self, result: dict, screenshot_path: Optional[str] = None):
        """
        Handle analysis result - send to output and save history

        Args:
            result: Analysis result dict from AIService
            screenshot_path: Optional path to saved screenshot
        """
        try:
            # Send to configured output
            self.strategy.send(result, screenshot_path)

            # Save to history if configured
            if self.config.save_history:
                self._save_to_history(result, screenshot_path)

        except Exception as e:
            logger.error(f"Error handling result: {e}")

    def _save_to_history(self, result: dict, screenshot_path: Optional[str] = None):
        """Save result to JSON history file"""
        try:
            history_file = self.config.log_dir / "history.jsonl"

            # Add screenshot path to result
            history_entry = result.copy()
            if screenshot_path:
                history_entry['screenshot_path'] = screenshot_path

            # Append to JSONL file (one JSON object per line)
            with open(history_file, 'a') as f:
                f.write(json.dumps(history_entry) + '\n')

            logger.debug(f"Result saved to history: {history_file}")

        except Exception as e:
            logger.error(f"Failed to save to history: {e}")


class Logger:
    """Utility class for structured logging"""

    @staticmethod
    def setup_logging(config):
        """Setup logging configuration"""
        log_level = getattr(logging, config.log_level.upper(), logging.INFO)

        # Basic configuration
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Silence noisy loggers from external libraries
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)

        # Add file handler if configured
        if config.save_to_file:
            log_file = config.log_dir / f"examsGPT_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            logging.getLogger().addHandler(file_handler)

        logger.info("Logging configured successfully")
