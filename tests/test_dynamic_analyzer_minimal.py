"""Tests for minimal dynamic analysis mode."""

from pathlib import Path
from types import SimpleNamespace

from modules.screenshot_manager.manager import Screenshot
from modules.exploration_strategy.explorer import ExplorationResult
import workers.dynamic_analyzer as dynamic_analyzer


class _FakeAndroidRunner:
    def connect_remote_emulator(self, host, port):
        return True


class _FakeTrafficMonitor:
    def __init__(self):
        self.started = False

    def set_whitelist(self, domains):
        return None

    def set_filter_policy(self, policy):
        return None

    def start(self, **kwargs):
        self.started = True

    def stop(self):
        self.started = False

    def get_requests(self):
        return []

    def get_requests_as_dict(self):
        return [
            {
                "url": "https://api.demo.com/v1/home",
                "method": "GET",
                "host": "api.demo.com",
                "path": "/v1/home",
                "source": "okhttp",
            }
        ]

    def get_aggregated_requests(self):
        return [{"host": "api.demo.com", "path": "/v1/home", "method": "GET", "count": 1}]

    def analyze_traffic(self):
        return {"total_requests": 1, "hosts": ["api.demo.com"]}


class _FakeAppExplorer:
    def __init__(self, ai_driver, android_runner, screenshot_manager, policy):
        self.screenshot_manager = screenshot_manager
        self.screenshot_manager.screenshots.append(
            Screenshot(
                stage="launch",
                description="fake launch",
                image_data=b"\x89PNG\r\n\x1a\nFAKE",
                timestamp="2026-02-22T00:00:00",
                image_hash="abc",
            )
        )

    def run_full_exploration(self, emulator_config, apk_info, persist_screenshots="minio", local_screenshot_dir=None):
        shot = self.screenshot_manager.screenshots[0]
        if local_screenshot_dir:
            self.screenshot_manager.save_to_local(shot, local_screenshot_dir, 0)
        return ExplorationResult(
            total_steps=3,
            screenshots=self.screenshot_manager.get_all_for_report(),
            network_requests=[],
            activities_visited=["com.demo/.MainActivity"],
            success=True,
            phases_completed=["setup", "autonomous"],
        )


class _FakeDomainAnalyzer:
    def analyze(self, requests):
        return []

    def generate_domain_report(self, domains):
        return {"master_domains": []}


def test_run_dynamic_analysis_minimal_writes_local_markdown(monkeypatch, tmp_path):
    apk_path = tmp_path / "sample.apk"
    apk_path.write_bytes(b"apk")

    monkeypatch.setattr(dynamic_analyzer, "AndroidRunner", _FakeAndroidRunner)
    monkeypatch.setattr(dynamic_analyzer, "TrafficMonitor", _FakeTrafficMonitor)
    monkeypatch.setattr(dynamic_analyzer, "AppExplorer", _FakeAppExplorer)
    monkeypatch.setattr(dynamic_analyzer, "MasterDomainAnalyzer", _FakeDomainAnalyzer)
    monkeypatch.setattr(dynamic_analyzer, "AIDriver", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(dynamic_analyzer, "_detect_package_name", lambda path: "com.demo.app")

    result = dynamic_analyzer.run_dynamic_analysis_minimal(
        apk_path=str(apk_path),
        output_dir=str(tmp_path / "out"),
        max_steps=3,
    )

    report_path = Path(result["report_path"])
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "# Minimal Dynamic Analysis Report" in text
    assert "com.demo.app" in text
    assert "api.demo.com" in text
    assert result["status"] == "success"
