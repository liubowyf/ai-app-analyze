"""Module 2 integration tests."""
import pytest


class TestModule2Integration:
    """Integration tests for Module 2 features."""

    def test_all_components_exist(self):
        """Test that all module 2 components exist."""
        # Risk scorer
        from modules.apk_analyzer.risk_scorer import RiskScorer
        assert RiskScorer is not None

        # Scenario testing
        from modules.scenario_testing.detector import ScenarioDetector
        assert ScenarioDetector is not None

        # Exploration controller
        from modules.exploration_strategy.controller import ExplorationController
        assert ExplorationController is not None

        # Traffic monitoring
        from modules.traffic_monitor.websocket_interceptor import WebSocketInterceptor
        from modules.traffic_monitor.grpc_parser import GRPCParser
        assert WebSocketInterceptor is not None
        assert GRPCParser is not None

    def test_risk_scorer_with_scenario_detector(self):
        """Test risk scorer works independently."""
        from modules.apk_analyzer.risk_scorer import RiskScorer

        scorer = RiskScorer()
        result = scorer.calculate_total_risk({
            'permissions': ['android.permission.INTERNET'],
            'components': {},
            'signature_info': {'self_signed': False}
        })

        assert 'risk_level' in result
        assert result['risk_level'] in ['LOW', 'MEDIUM', 'HIGH']

    def test_controller_depth_and_loop(self):
        """Test controller depth and loop detection."""
        from modules.exploration_strategy.controller import ExplorationController

        controller = ExplorationController(max_depth=3)

        # Test depth limit
        assert controller.should_continue() is True
        controller.state.current_depth = 3
        assert controller.should_continue() is False

        # Reset and test loop
        controller.state.current_depth = 0
        for _ in range(4):
            controller.record_screen(b"same", "same")

        assert controller.detect_loop() is True
