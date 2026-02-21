"""Feature extraction for domain classification."""
import re
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class DomainFeatureExtractor:
    """Extract features from domain names for ML classification."""

    def extract_features(self, domain: str) -> Dict:
        """
        Extract features from a domain name.

        Args:
            domain: Domain name to analyze

        Returns:
            Dict with extracted features
        """
        features = {}

        # Basic features
        features['domain_length'] = len(domain)
        features['num_dots'] = domain.count('.')
        features['num_hyphens'] = domain.count('-')

        # Number features
        numbers = re.findall(r'\d', domain)
        features['has_numbers'] = len(numbers) > 0
        features['num_numbers'] = len(numbers)

        # TLD features
        parts = domain.split('.')
        if len(parts) >= 2:
            tld = parts[-1]
            features['tld_length'] = len(tld)
            features['tld'] = tld
        else:
            features['tld_length'] = 0
            features['tld'] = ''

        # IP address features
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        features['is_ip'] = bool(re.match(ip_pattern, domain))

        if features['is_ip']:
            features['is_private_ip'] = self._is_private_ip(domain)
        else:
            features['is_private_ip'] = False

        # Subdomain features
        features['num_subdomains'] = max(0, len(parts) - 2)
        features['has_www'] = domain.startswith('www.')

        # Character diversity
        unique_chars = set(domain.lower())
        features['unique_char_ratio'] = len(unique_chars) / len(domain) if domain else 0

        return features

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is private."""
        try:
            parts = [int(p) for p in ip.split('.')]
            if parts[0] == 10:
                return True
            if parts[0] == 172 and 16 <= parts[1] <= 31:
                return True
            if parts[0] == 192 and parts[1] == 168:
                return True
        except Exception:
            pass
        return False
