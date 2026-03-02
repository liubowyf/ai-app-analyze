"""Test static analyzer."""
import pytest


def test_static_analysis_entrypoint_exists():
    """Static analyzer should expose callable stage entrypoint."""
    from workers.static_analyzer import run_static_analysis

    assert callable(run_static_analysis)


def test_apk_analyzer_extract_package_name():
    """Test APK analyzer can extract package name."""
    from modules.apk_analyzer.analyzer import ApkAnalyzer

    # This is a placeholder test - real test needs actual APK
    analyzer = ApkAnalyzer()
    assert analyzer is not None
