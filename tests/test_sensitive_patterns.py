"""Test sensitive data pattern detection."""
import pytest
from modules.domain_analyzer.sensitive_patterns import SensitivePatternDetector


class TestSensitivePatternDetector:
    """Test sensitive data detection."""

    def test_detect_phone_number(self):
        """Test phone number detection."""
        detector = SensitivePatternDetector()

        text = "user_phone=13812345678"
        matches = detector.detect(text)

        assert len(matches) > 0
        assert matches[0]['type'] == 'phone_number'

    def test_detect_email(self):
        """Test email detection."""
        detector = SensitivePatternDetector()

        text = "email=user@example.com"
        matches = detector.detect(text)

        assert len(matches) > 0
        assert matches[0]['type'] == 'email'

    def test_detect_id_card(self):
        """Test ID card detection."""
        detector = SensitivePatternDetector()

        text = "id_card=110101199001011234"
        matches = detector.detect(text)

        assert len(matches) > 0
        assert matches[0]['type'] == 'id_card'

    def test_detect_token(self):
        """Test token detection."""
        detector = SensitivePatternDetector()

        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        matches = detector.detect(text)

        assert len(matches) > 0
        assert matches[0]['type'] == 'token'
