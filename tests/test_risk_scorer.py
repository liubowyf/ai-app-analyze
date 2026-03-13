"""Test risk scoring functionality."""
import pytest
from modules.apk_analyzer.risk_scorer import RiskScorer


class TestRiskScorer:
    """Test risk scorer."""

    def test_calculate_permission_risk_with_dangerous_permissions(self):
        """Test permission risk with dangerous permissions."""
        scorer = RiskScorer()
        permissions = [
            'android.permission.READ_CONTACTS',
            'android.permission.ACCESS_FINE_LOCATION',
            'android.permission.READ_SMS',
        ]
        score = scorer.calculate_permission_risk(permissions)
        assert score == 9  # 3 dangerous permissions × 3 points each

    def test_calculate_permission_risk_with_normal_permissions(self):
        """Test permission risk with normal permissions."""
        scorer = RiskScorer()
        permissions = [
            'android.permission.INTERNET',
            'android.permission.ACCESS_NETWORK_STATE',
        ]
        score = scorer.calculate_permission_risk(permissions)
        assert score == 2  # 2 normal permissions × 1 point each

    def test_calculate_permission_risk_empty(self):
        """Test permission risk with no permissions."""
        scorer = RiskScorer()
        score = scorer.calculate_permission_risk([])
        assert score == 0

    def test_calculate_component_risk_with_exported(self):
        """Test component risk with exported components."""
        scorer = RiskScorer()
        components = {
            'activities': [
                {'name': 'MainActivity', 'exported': True},
                {'name': 'SettingsActivity', 'exported': False},
            ],
            'receivers': [
                {'name': 'BootReceiver', 'exported': True}
            ]
        }
        score = scorer.calculate_component_risk(components)
        assert score == 4  # 2 exported components × 2 points each

    def test_calculate_component_risk_no_exported(self):
        """Test component risk with no exported components."""
        scorer = RiskScorer()
        components = {
            'activities': [{'name': 'MainActivity', 'exported': False}]
        }
        score = scorer.calculate_component_risk(components)
        assert score == 0

    def test_calculate_signature_risk_no_signature(self):
        """Test signature risk with no signature."""
        scorer = RiskScorer()
        score = scorer.calculate_signature_risk(None)
        assert score == 5

    def test_calculate_signature_risk_self_signed(self):
        """Test signature risk with self-signed cert."""
        scorer = RiskScorer()
        score = scorer.calculate_signature_risk({'self_signed': True})
        assert score == 2

    def test_calculate_signature_risk_proper(self):
        """Test signature risk with proper signature."""
        scorer = RiskScorer()
        score = scorer.calculate_signature_risk({'self_signed': False})
        assert score == 0

    def test_calculate_total_risk_high_risk(self):
        """Test total risk calculation for high-risk APK."""
        scorer = RiskScorer()
        analysis_result = {
            'permissions': [
                'android.permission.READ_CONTACTS',
                'android.permission.ACCESS_FINE_LOCATION',
                'android.permission.READ_SMS',
                'android.permission.CAMERA',  # Add one more to reach HIGH threshold
            ],
            'components': {
                'activities': [{'name': 'MainActivity', 'exported': True}],
                'receivers': [{'name': 'SmsReceiver', 'exported': True}]
            },
            'signature_info': None  # No signature
        }
        result = scorer.calculate_total_risk(analysis_result)

        assert result['risk_level'] == "HIGH"
        assert result['total_score'] >= 20
        assert 'breakdown' in result
        assert result['breakdown']['permission_risk'] == 12
        assert result['breakdown']['component_risk'] == 4
        assert result['breakdown']['signature_risk'] == 5

    def test_calculate_total_risk_low_risk(self):
        """Test total risk calculation for low-risk APK."""
        scorer = RiskScorer()
        analysis_result = {
            'permissions': ['android.permission.INTERNET'],
            'components': {
                'activities': [{'name': 'MainActivity', 'exported': False}]
            },
            'signature_info': {'self_signed': False}
        }
        result = scorer.calculate_total_risk(analysis_result)

        assert result['risk_level'] == "LOW"
        assert result['total_score'] < 10
        assert result['breakdown']['permission_risk'] == 1
        assert result['breakdown']['component_risk'] == 0
        assert result['breakdown']['signature_risk'] == 0
