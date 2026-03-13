"""ML-based domain classifier."""
import logging
from typing import Dict, List, Optional
import pickle
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from .feature_extractor import DomainFeatureExtractor

logger = logging.getLogger(__name__)


class MLDomainClassifier:
    """Machine learning classifier for domain classification."""

    def __init__(self):
        """Initialize classifier."""
        self.feature_extractor = DomainFeatureExtractor()
        self.vectorizer = None
        self.model = None
        self.is_trained = False

        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, classifier will not work")

    def train(self, training_data: List[Dict]) -> None:
        """
        Train the classifier.

        Args:
            training_data: List of dicts with 'domain' and 'label' keys
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn not available")

        # Extract features
        features_list = []
        labels = []

        for item in training_data:
            features = self.feature_extractor.extract_features(item['domain'])
            features_list.append(features)
            labels.append(item['label'])

        # Vectorize features
        self.vectorizer = DictVectorizer(sparse=False)
        X = self.vectorizer.fit_transform(features_list)

        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X, labels)

        self.is_trained = True
        logger.info(f"Trained classifier on {len(training_data)} samples")

    def predict(self, domain: str) -> Dict:
        """
        Predict domain type.

        Args:
            domain: Domain name to classify

        Returns:
            Dict with 'label' and 'confidence'
        """
        if not self.is_trained:
            raise RuntimeError("Classifier not trained")

        # Extract features
        features = self.feature_extractor.extract_features(domain)

        # Vectorize
        X = self.vectorizer.transform([features])

        # Predict
        label = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]

        # Get confidence for predicted class
        class_idx = list(self.model.classes_).index(label)
        confidence = probabilities[class_idx]

        return {
            'label': label,
            'confidence': float(confidence)
        }

    def save(self, filepath: str) -> None:
        """Save trained model to file."""
        if not self.is_trained:
            raise RuntimeError("Classifier not trained")

        model_data = {
            'model': self.model,
            'vectorizer': self.vectorizer
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Saved model to {filepath}")

    def load(self, filepath: str) -> None:
        """Load trained model from file."""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.vectorizer = model_data['vectorizer']
        self.is_trained = True

        logger.info(f"Loaded model from {filepath}")
