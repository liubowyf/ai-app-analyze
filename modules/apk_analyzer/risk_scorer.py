"""APK risk scoring module."""
from typing import List, Dict


class RiskScorer:
    """Calculate risk scores for APK files."""

    # Dangerous permissions that pose higher security risks
    DANGEROUS_PERMISSIONS = [
        'android.permission.READ_CONTACTS',
        'android.permission.ACCESS_FINE_LOCATION',
        'android.permission.ACCESS_COARSE_LOCATION',
        'android.permission.READ_SMS',
        'android.permission.SEND_SMS',
        'android.permission.RECEIVE_SMS',
        'android.permission.CALL_PHONE',
        'android.permission.READ_CALL_LOG',
        'android.permission.WRITE_CALL_LOG',
        'android.permission.READ_PHONE_STATE',
        'android.permission.CAMERA',
        'android.permission.RECORD_AUDIO',
        'android.permission.READ_EXTERNAL_STORAGE',
        'android.permission.WRITE_EXTERNAL_STORAGE',
    ]

    def calculate_permission_risk(self, permissions: List[str]) -> int:
        """
        Calculate risk score based on permissions.

        Args:
            permissions: List of permission strings

        Returns:
            int: Risk score
        """
        score = 0
        for perm in permissions:
            if perm in self.DANGEROUS_PERMISSIONS:
                score += 3  # Dangerous permission
            else:
                score += 1  # Normal permission
        return score

    def calculate_component_risk(self, components: Dict) -> int:
        """
        Calculate risk score based on exported components.

        Args:
            components: Dict with component types as keys

        Returns:
            int: Risk score
        """
        score = 0
        for component_type, items in components.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get('exported', False):
                        score += 2  # Exported component
        return score

    def calculate_signature_risk(self, signature_info: Dict) -> int:
        """
        Calculate risk score based on signature.

        Args:
            signature_info: Signature information dict

        Returns:
            int: Risk score
        """
        if not signature_info:
            return 5  # No signature, high risk

        if signature_info.get('self_signed', False):
            return 2  # Self-signed, medium risk

        return 0  # Properly signed, no risk

    def calculate_total_risk(self, analysis_result: Dict) -> Dict:
        """
        Calculate total risk assessment.

        Args:
            analysis_result: Complete analysis result dict

        Returns:
            Dict with total score, risk level, and breakdown
        """
        permission_risk = self.calculate_permission_risk(
            analysis_result.get('permissions', [])
        )
        component_risk = self.calculate_component_risk(
            analysis_result.get('components', {})
        )
        signature_risk = self.calculate_signature_risk(
            analysis_result.get('signature_info', {})
        )

        total_score = permission_risk + component_risk + signature_risk

        # Determine risk level
        if total_score >= 20:
            risk_level = "HIGH"
        elif total_score >= 10:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "total_score": total_score,
            "risk_level": risk_level,
            "breakdown": {
                "permission_risk": permission_risk,
                "component_risk": component_risk,
                "signature_risk": signature_risk
            }
        }
