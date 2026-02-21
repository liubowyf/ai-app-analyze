"""Test ML domain classifier."""
import pytest
from modules.domain_analyzer.ml_classifier import MLDomainClassifier
from modules.domain_analyzer.training_data import TrainingDataGenerator


class TestMLDomainClassifier:
    """Test ML domain classifier."""

    def test_classifier_training(self):
        """Test classifier can be trained."""
        classifier = MLDomainClassifier()
        generator = TrainingDataGenerator()

        training_data = generator.generate_training_data(100)

        classifier.train(training_data)

        assert classifier.is_trained is True

    def test_classifier_prediction(self):
        """Test classifier can predict domain type."""
        classifier = MLDomainClassifier()
        generator = TrainingDataGenerator()

        training_data = generator.generate_training_data(100)
        classifier.train(training_data)

        prediction = classifier.predict("cdn.example.com")

        assert 'label' in prediction
        assert 'confidence' in prediction
        assert prediction['label'] in ['master', 'cdn', 'tracker', 'normal']
        assert 0 <= prediction['confidence'] <= 1

    def test_classifier_accuracy(self):
        """Test classifier achieves acceptable accuracy."""
        classifier = MLDomainClassifier()
        generator = TrainingDataGenerator()

        training_data = generator.generate_training_data(200)
        test_data = generator.generate_training_data(50)

        classifier.train(training_data)

        correct = 0
        for item in test_data:
            pred = classifier.predict(item['domain'])
            if pred['label'] == item['label']:
                correct += 1

        accuracy = correct / len(test_data)
        assert accuracy >= 0.7  # At least 70% accuracy
