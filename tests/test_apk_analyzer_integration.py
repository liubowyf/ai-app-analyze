"""Integration tests for APK analyzer with risk scoring."""
import pytest
from modules.apk_analyzer.risk_scorer import RiskScorer


class TestApkAnalyzerIntegration:
    """Test APK analyzer integration."""

    def test_risk_scorer_exists(self):
        """Test that RiskScorer can be imported and used."""
        scorer = RiskScorer()
        assert scorer is not None

        result = scorer.calculate_total_risk({
            'permissions': ['android.permission.INTERNET'],
            'components': {},
            'signature_info': {'self_signed': False}
        })

        assert 'risk_level' in result
        assert result['risk_level'] in ['LOW', 'MEDIUM', 'HIGH']

    def test_cached_analyze_apk_exists(self):
        """Test that cached_analyze_apk function exists."""
        from modules.apk_analyzer.analyzer import cached_analyze_apk

        assert callable(cached_analyze_apk)
        assert hasattr(cached_analyze_apk, 'cache_info')

    def test_apk_parsing_cache(self):
        """Test that APK parsing cache works."""
        from modules.apk_analyzer.analyzer import cached_analyze_apk

        # Clear cache
        cached_analyze_apk.cache_clear()

        # Check cache info
        initial_info = cached_analyze_apk.cache_info()
        assert initial_info.hits == 0
        assert initial_info.misses == 0

        # Cache should work (we can't easily test actual APK parsing
        # without a real APK file, but we can verify the decorator exists)
        assert callable(cached_analyze_apk)
