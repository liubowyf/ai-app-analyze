"""Scenario detection for dynamic analysis."""
from typing import List
from dataclasses import dataclass


@dataclass
class UIElement:
    """UI element representation."""
    text: str
    class_name: str
    bounds: dict
    clickable: bool
    editable: bool


class ScenarioDetector:
    """Detect specific UI scenarios."""

    def detect_login(self, ui_elements: List[UIElement]) -> bool:
        """
        Detect login scenario.

        Detection rules:
        1. Has login button (text contains '登录', 'login', 'sign in')
        2. Has username/phone input (text contains '用户名', '手机号', 'username')
        3. Has password input (class_name contains 'password')

        Args:
            ui_elements: List of UI elements

        Returns:
            bool: True if login scenario detected
        """
        has_login_button = False
        has_username_input = False
        has_password_input = False

        for element in ui_elements:
            # Check for login button
            if element.clickable and any(
                keyword in element.text.lower()
                for keyword in ['登录', 'login', 'sign in']
            ):
                has_login_button = True

            # Check for username input
            if element.editable and any(
                keyword in element.text.lower()
                for keyword in ['用户名', '手机号', 'username', 'phone']
            ):
                has_username_input = True

            # Check for password input
            if element.editable and 'password' in element.class_name.lower():
                has_password_input = True

        return has_login_button and (has_username_input or has_password_input)

    def detect_payment(self, ui_elements: List[UIElement]) -> bool:
        """Detect payment scenario."""
        has_payment_button = False
        has_amount_input = False
        has_payment_method = False

        for element in ui_elements:
            if element.clickable and any(
                keyword in element.text.lower()
                for keyword in ['支付', '付款', 'pay', 'payment']
            ):
                has_payment_button = True

            if element.editable and any(
                keyword in element.text.lower()
                for keyword in ['金额', 'amount', 'price']
            ):
                has_amount_input = True

            if any(
                keyword in element.text.lower()
                for keyword in ['微信', '支付宝', 'wechat', 'alipay']
            ):
                has_payment_method = True

        return has_payment_button or (has_amount_input and has_payment_method)

    def detect_share(self, ui_elements: List[UIElement]) -> bool:
        """Detect share scenario."""
        has_share_button = False
        has_share_platform = False

        for element in ui_elements:
            if element.clickable and any(
                keyword in element.text.lower()
                for keyword in ['分享', 'share']
            ):
                has_share_button = True

            if any(
                keyword in element.text.lower()
                for keyword in ['微信', 'qq', '微博', 'wechat', 'weibo']
            ):
                has_share_platform = True

        return has_share_button or has_share_platform
