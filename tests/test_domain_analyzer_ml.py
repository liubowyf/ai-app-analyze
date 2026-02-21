"""Test ML integration with domain analyzer."""
import pytest
from modules.domain_analyzer.analyzer import MasterDomainAnalyzer
from modules.domain_analyzer.training_data import TrainingDataGenerator


class TestDomainAnalyzerML:
    """Test ML integration."""

    def test_analyzer_uses_ml_when_available(self):
        """Test analyzer uses ML model when available."""
        analyzer = MasterDomainAnalyzer()

        # Train ML model
        generator = TrainingDataGenerator()
        training_data = generator.generate_training_data(100)
        analyzer.train_ml_model(training_data)

        # Analyze domain
        result = analyzer.analyze_domain("cdn.example.com")

        assert 'ml_prediction' in result
        assert result['ml_prediction']['label'] in ['master', 'cdn', 'tracker', 'normal']
