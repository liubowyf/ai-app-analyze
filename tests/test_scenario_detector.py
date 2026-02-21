"""Test scenario detection."""
import pytest
from modules.scenario_testing.detector import ScenarioDetector, UIElement


class TestScenarioDetector:
    """Test scenario detector."""

    @pytest.fixture
    def detector(self):
        """Create detector instance."""
        return ScenarioDetector()

    def test_detect_login_scenario(self, detector):
        """Test login scenario detection."""
        ui_elements = [
            UIElement(text="登录", class_name="Button", bounds={}, clickable=True, editable=False),
            UIElement(text="用户名", class_name="EditText", bounds={}, clickable=False, editable=True),
            UIElement(text="密码", class_name="EditText", bounds={}, clickable=False, editable=True),
        ]

        result = detector.detect_login(ui_elements)
        assert result is True

    def test_detect_login_scenario_not_found(self, detector):
        """Test when login scenario not found."""
        ui_elements = [
            UIElement(text="设置", class_name="Button", bounds={}, clickable=True, editable=False),
        ]

        result = detector.detect_login(ui_elements)
        assert result is False

    def test_detect_payment_scenario(self, detector):
        """Test payment scenario detection."""
        ui_elements = [
            UIElement(text="支付", class_name="Button", bounds={}, clickable=True, editable=False),
            UIElement(text="金额", class_name="EditText", bounds={}, clickable=False, editable=True),
            UIElement(text="微信支付", class_name="RadioButton", bounds={}, clickable=True, editable=False),
        ]

        result = detector.detect_payment(ui_elements)
        assert result is True

    def test_detect_payment_scenario_with_amount_and_method(self, detector):
        """Test payment detection with amount input and payment method."""
        ui_elements = [
            UIElement(text="金额", class_name="EditText", bounds={}, clickable=False, editable=True),
            UIElement(text="支付宝", class_name="ImageView", bounds={}, clickable=True, editable=False),
        ]

        result = detector.detect_payment(ui_elements)
        assert result is True

    def test_detect_share_scenario(self, detector):
        """Test share scenario detection."""
        ui_elements = [
            UIElement(text="分享", class_name="Button", bounds={}, clickable=True, editable=False),
            UIElement(text="微信", class_name="ImageView", bounds={}, clickable=True, editable=False),
        ]

        result = detector.detect_share(ui_elements)
        assert result is True

    def test_detect_share_scenario_platform_only(self, detector):
        """Test share detection with platform only."""
        ui_elements = [
            UIElement(text="分享到微博", class_name="TextView", bounds={}, clickable=False, editable=False),
        ]

        result = detector.detect_share(ui_elements)
        assert result is True
