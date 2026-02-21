"""Test threat intelligence integration."""
import pytest
from modules.domain_analyzer.threat_intel import ThreatIntelligenceClient


class TestThreatIntelligenceClient:
    """Test threat intelligence client."""

    def test_client_initialization(self):
        """Test client can be initialized."""
        client = ThreatIntelligenceClient()

        assert client is not None

    def test_query_domain_safe(self):
        """Test querying a safe domain."""
        client = ThreatIntelligenceClient()

        result = client.query_domain("google.com")

        assert 'is_malicious' in result
        assert result['is_malicious'] is False

    def test_query_domain_with_cache(self):
        """Test query result is cached."""
        client = ThreatIntelligenceClient()

        # First query
        result1 = client.query_domain("example.com")

        # Second query (should use cache)
        result2 = client.query_domain("example.com")

        assert result1 == result2
