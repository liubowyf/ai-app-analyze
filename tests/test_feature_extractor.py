"""Test feature extractor for domain classification."""
import pytest
from modules.domain_analyzer.feature_extractor import DomainFeatureExtractor


class TestDomainFeatureExtractor:
    """Test domain feature extraction."""

    def test_extract_features_from_domain(self):
        """Test feature extraction from domain name."""
        extractor = DomainFeatureExtractor()

        features = extractor.extract_features("api.example.com")

        assert 'domain_length' in features
        assert 'num_dots' in features
        assert 'has_numbers' in features
        assert 'tld_length' in features
        assert features['domain_length'] == 15
        assert features['num_dots'] == 2
        assert features['has_numbers'] is False

    def test_extract_features_with_numbers(self):
        """Test feature extraction from domain with numbers."""
        extractor = DomainFeatureExtractor()

        features = extractor.extract_features("api123.example.com")

        assert features['has_numbers'] is True
        assert features['num_numbers'] == 3

    def test_extract_features_from_ip(self):
        """Test feature extraction from IP address."""
        extractor = DomainFeatureExtractor()

        features = extractor.extract_features("192.168.1.1")

        assert features['is_ip'] is True
        assert features['is_private_ip'] is True
