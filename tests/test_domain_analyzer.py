"""Tests for MasterDomainAnalyzer."""
import pytest
from modules.domain_analyzer.analyzer import MasterDomainAnalyzer, DomainScore
from datetime import datetime


def test_analyzer_initialization():
    """Test analyzer initialization."""
    analyzer = MasterDomainAnalyzer()
    assert analyzer is not None


def test_is_cdn_domain():
    """Test CDN domain detection."""
    analyzer = MasterDomainAnalyzer()

    assert analyzer.is_cdn_domain("cdn.example.com")
    assert analyzer.is_cdn_domain("d12345.cloudfront.net")
    assert not analyzer.is_cdn_domain("api.example.com")


def test_calculate_domain_score():
    """Test domain scoring."""
    analyzer = MasterDomainAnalyzer()

    # Mock request data
    from modules.traffic_monitor import NetworkRequest

    request = NetworkRequest(
        url="https://api.example.com/v1/user",
        method="POST",
        host="api.example.com",
        path="/v1/user",
        ip="1.2.3.4",
        port=443,
        scheme="https",
        request_time=datetime.now(),
        response_code=200,
        content_type="application/json",
        request_headers={},
        response_headers={},
        request_body='{"user_id": "123"}',
        response_body=None
    )

    score = analyzer.calculate_domain_score("api.example.com", [request])
    assert score.score > 0
    assert score.domain == "api.example.com"
    assert score.request_count == 1
    assert score.post_count == 1
    assert score.has_sensitive_data is True
