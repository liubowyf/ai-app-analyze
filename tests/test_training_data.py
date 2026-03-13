"""Test training data generation."""
import pytest
from modules.domain_analyzer.training_data import TrainingDataGenerator


class TestTrainingDataGenerator:
    """Test training data generator."""

    def test_generate_labeled_data(self):
        """Test labeled data generation."""
        generator = TrainingDataGenerator()

        data = generator.generate_training_data(100)

        assert len(data) == 100
        assert all('domain' in item for item in data)
        assert all('label' in item for item in data)
        assert all(item['label'] in ['master', 'cdn', 'tracker', 'normal'] for item in data)

    def test_balanced_classes(self):
        """Test balanced class distribution."""
        generator = TrainingDataGenerator()

        data = generator.generate_training_data(100)

        labels = [item['label'] for item in data]
        label_counts = {}
        for label in labels:
            label_counts[label] = label_counts.get(label, 0) + 1

        # Each class should have at least 10% representation
        for label, count in label_counts.items():
            assert count >= 10
