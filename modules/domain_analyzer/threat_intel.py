"""Threat intelligence integration."""
import logging
import hashlib
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ThreatIntelligenceClient:
    """Client for querying threat intelligence APIs."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize client.

        Args:
            api_key: API key for threat intelligence service
        """
        self.api_key = api_key
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = timedelta(hours=24)

    def query_domain(self, domain: str) -> Dict:
        """
        Query threat intelligence for a domain.

        Args:
            domain: Domain to query

        Returns:
            Dict with threat intelligence results
        """
        # Check cache
        if domain in self.cache:
            cached = self.cache[domain]
            if datetime.now() - cached['timestamp'] < self.cache_ttl:
                logger.debug(f"Cache hit for {domain}")
                return cached['result']

        # Query threat intelligence API
        result = self._query_api(domain)

        # Cache result
        self.cache[domain] = {
            'result': result,
            'timestamp': datetime.now()
        }

        return result

    def _query_api(self, domain: str) -> Dict:
        """
        Query external API (mock implementation).

        Args:
            domain: Domain to query

        Returns:
            Dict with API results
        """
        # Mock implementation - in production, call real API
        # For now, return safe result for known domains
        safe_domains = ['google.com', 'example.com', 'github.com']

        result = {
            'domain': domain,
            'is_malicious': domain not in safe_domains,
            'threat_score': 0 if domain in safe_domains else 50,
            'threat_types': [],
            'last_seen': datetime.now().isoformat(),
            'sources': ['mock_api']
        }

        if result['is_malicious']:
            result['threat_types'] = ['suspicious']
            logger.warning(f"Domain {domain} flagged as malicious")

        return result

    def clear_cache(self):
        """Clear the cache."""
        self.cache.clear()
        logger.info("Cleared threat intelligence cache")
