"""
Screenshot queue management for multi-image analysis
"""
import logging
from datetime import datetime
from typing import Optional
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
