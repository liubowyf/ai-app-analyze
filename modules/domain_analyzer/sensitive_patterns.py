"""Sensitive data pattern detection."""
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class SensitivePatternDetector:
    """Detect sensitive data patterns in text."""

    # Pattern definitions (order matters - more specific patterns first)
    PATTERNS = {
        'token': {
            'pattern': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
            'description': 'JWT token'
        },
        'id_card': {
            'pattern': r'\d{17}[\dXx]',
            'description': 'Chinese ID card number'
        },
        'phone_number': {
            'pattern': r'1[3-9]\d{9}',
            'description': 'Chinese mobile phone number'
        },
        'email': {
            'pattern': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'description': 'Email address'
        },
        'bank_card': {
            'pattern': r'\d{16,19}',
            'description': 'Bank card number'
        },
        'api_key': {
            'pattern': r'[a-zA-Z0-9]{32,45}',
            'description': 'API key'
        },
        'password': {
            'pattern': r'(password|passwd|pwd)[=:]\s*\S+',
            'description': 'Password field'
        },
        'imei': {
            'pattern': r'\d{15}',
            'description': 'IMEI number'
        },
        'mac_address': {
            'pattern': r'([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}',
            'description': 'MAC address'
        },
        'ip_address': {
            'pattern': r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
            'description': 'IP address'
        }
    }

    def __init__(self):
        """Initialize detector."""
        self.compiled_patterns = {}
        for name, config in self.PATTERNS.items():
            self.compiled_patterns[name] = re.compile(config['pattern'])

    def detect(self, text: str) -> List[Dict]:
        """
        Detect sensitive data in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected sensitive data
        """
        matches = []
        matched_positions = set()  # Track already matched positions

        for name, pattern in self.compiled_patterns.items():
            for match in pattern.finditer(text):
                # Check if this position was already matched by a more specific pattern
                positions = range(match.start(), match.end())
                if any(pos in matched_positions for pos in positions):
                    continue  # Skip overlapping matches

                # Mark these positions as matched
                matched_positions.update(positions)

                matches.append({
                    'type': name,
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'description': self.PATTERNS[name]['description']
                })

        return matches

    def mask_sensitive_data(self, text: str) -> str:
        """
        Mask sensitive data in text.

        Args:
            text: Text to mask

        Returns:
            Text with sensitive data masked
        """
        masked = text

        for name, pattern in self.compiled_patterns.items():
            matches = list(pattern.finditer(masked))
            # Replace from end to preserve positions
            for match in reversed(matches):
                value = match.group()
                masked_value = self._mask_value(value, name)
                masked = masked[:match.start()] + masked_value + masked[match.end():]

        return masked

    def _mask_value(self, value: str, data_type: str) -> str:
        """Mask a sensitive value."""
        if len(value) <= 4:
            return '*' * len(value)

        # Show first 2 and last 2 chars
        return value[:2] + '*' * (len(value) - 4) + value[-2:]
