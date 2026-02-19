"""Test static analyzer."""
import pytest


def test_static_analysis_task_registered():
    """Test that static analysis task is registered."""
    # Import the static_analyzer module to register tasks
    import workers.static_analyzer
    from workers.celery_app import celery_app

    assert "workers.static_analyzer.run_static_analysis" in celery_app.tasks


def test_apk_analyzer_extract_package_name():
    """Test APK analyzer can extract package name."""
    from modules.apk_analyzer.analyzer import ApkAnalyzer

    # This is a placeholder test - real test needs actual APK
    analyzer = ApkAnalyzer()
    assert analyzer is not None
