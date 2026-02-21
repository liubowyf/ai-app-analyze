"""Exploration controller for managing exploration depth and loops."""
from typing import List
from dataclasses import dataclass, field
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExplorationState:
    """Exploration state tracking."""
    current_depth: int = 0
    max_depth: int = 50
    visited_screens: List[str] = field(default_factory=list)
    screen_hash_history: List[str] = field(default_factory=list)


class ExplorationController:
    """Control exploration depth and detect loops."""

    def __init__(self, max_depth: int = 50):
        """
        Initialize controller.

        Args:
            max_depth: Maximum exploration depth
        """
        self.state = ExplorationState(max_depth=max_depth)
        self.loop_detection_window = 10
        self.loop_threshold = 3

    def should_continue(self) -> bool:
        """
        Check if exploration should continue.

        Returns:
            bool: True if should continue, False to stop
        """
        if self.state.current_depth >= self.state.max_depth:
            logger.warning(
                f"Reached max exploration depth {self.state.max_depth}"
            )
            return False

        return True

    def record_screen(self, screenshot: bytes, screen_description: str):
        """
        Record visited screen.

        Args:
            screenshot: Screenshot bytes
            screen_description: Screen description text
        """
        screen_hash = hashlib.md5(screenshot).hexdigest()

        self.state.screen_hash_history.append(screen_hash)
        self.state.visited_screens.append(screen_description)
        self.state.current_depth += 1

        logger.debug(
            f"Recorded screen: depth={self.state.current_depth}, "
            f"hash={screen_hash[:8]}"
        )

    def detect_loop(self) -> bool:
        """
        Detect if stuck in a loop.

        Returns:
            bool: True if loop detected
        """
        if len(self.state.screen_hash_history) < self.loop_threshold:
            return False

        recent_hashes = self.state.screen_hash_history[-self.loop_detection_window:]
        hash_counts = {}

        for h in recent_hashes:
            hash_counts[h] = hash_counts.get(h, 0) + 1

        for h, count in hash_counts.items():
            if count >= self.loop_threshold:
                logger.warning(f"Loop detected: hash={h[:8]}, count={count}")
                return True

        return False

    def get_backtrack_strategy(self) -> str:
        """
        Get backtrack strategy.

        Returns:
            str: Strategy ('back', 'restart', 'skip')
        """
        if self.detect_loop():
            return 'back'

        if self.state.current_depth >= self.state.max_depth - 5:
            return 'skip'

        return 'back'
