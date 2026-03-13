"""Test exploration controller."""
import pytest
from modules.exploration_strategy.controller import ExplorationController, ExplorationState


class TestExplorationController:
    """Test exploration controller."""

    def test_exploration_state_initialization(self):
        """Test state initialization."""
        state = ExplorationState(max_depth=50)

        assert state.current_depth == 0
        assert state.max_depth == 50
        assert state.visited_screens == []
        assert state.screen_hash_history == []

    def test_should_continue_below_max_depth(self):
        """Test continuation when below max depth."""
        controller = ExplorationController(max_depth=5)

        assert controller.should_continue() is True

        # Simulate exploring
        controller.state.current_depth = 4
        assert controller.should_continue() is True

    def test_should_stop_at_max_depth(self):
        """Test stop when reaching max depth."""
        controller = ExplorationController(max_depth=5)

        controller.state.current_depth = 5
        assert controller.should_continue() is False

        controller.state.current_depth = 6
        assert controller.should_continue() is False

    def test_detect_loop_no_loop(self):
        """Test no loop detected with unique screens."""
        controller = ExplorationController()

        # Record unique screens
        for i in range(10):
            controller.record_screen(f"screen_{i}".encode(), f"description_{i}")

        assert controller.detect_loop() is False

    def test_detect_loop_with_repetition(self):
        """Test loop detection with repeated screen."""
        controller = ExplorationController()

        # Record same screen multiple times
        same_screen = b"same_screen_content"
        for _ in range(5):
            controller.record_screen(same_screen, "same_screen")

        assert controller.detect_loop() is True

    def test_get_backtrack_strategy_loop(self):
        """Test backtrack strategy when loop detected."""
        controller = ExplorationController()

        # Create loop
        for _ in range(3):
            controller.record_screen(b"loop_screen", "loop_screen")

        strategy = controller.get_backtrack_strategy()
        assert strategy == 'back'

    def test_get_backtrack_strategy_near_max(self):
        """Test backtrack strategy near max depth."""
        controller = ExplorationController(max_depth=10)

        # Reach near max depth
        controller.state.current_depth = 8

        strategy = controller.get_backtrack_strategy()
        assert strategy == 'skip'

    def test_record_screen_increments_depth(self):
        """Test that recording screen increments depth."""
        controller = ExplorationController()

        assert controller.state.current_depth == 0

        controller.record_screen(b"screen1", "desc1")
        assert controller.state.current_depth == 1

        controller.record_screen(b"screen2", "desc2")
        assert controller.state.current_depth == 2

        assert len(controller.state.visited_screens) == 2
        assert len(controller.state.screen_hash_history) == 2
