"""Tests for minimal dynamic analysis mode."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from modules.screenshot_manager.manager import Screenshot
from modules.exploration_strategy.explorer import ExplorationResult
import workers.dynamic_analyzer as dynamic_analyzer


class _FakeAndroidRunner:
    def connect_remote_emulator(self, host, port):
        return True


class _FakeTrafficMonitor:
    def __init__(self, *args, **kwargs):
        self.started = False
        self.proxy_port = kwargs.get("proxy_port")

    def set_whitelist(self, domains):
        return None

    def set_filter_policy(self, policy):
        return None

    def start(self, **kwargs):
        self.started = True

    def stop(self):
        self.started = False

    def get_requests(self):
        return [SimpleNamespace(host="api.demo.com")]

    def get_candidate_requests(self):
        return [SimpleNamespace(host="edge.demo.com")]

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

    def get_candidate_requests_as_dict(self):
        return [
            {
                "url": "https://edge.demo.com/candidate",
                "method": "GET",
                "host": "edge.demo.com",
                "path": "/candidate",
                "source": "webview",
                "attribution_confidence": 0.5,
            }
        ]

    def get_candidate_aggregated_requests(self):
        return [{"host": "edge.demo.com", "path": "/candidate", "method": "GET", "count": 1}]

    def analyze_traffic(self):
        return {
            "total_requests": 1,
            "hosts": ["api.demo.com"],
            "candidate_total_requests": 1,
            "candidate_unique_hosts": 1,
            "candidate_sources": {"webview": 1},
            "cert_verification_status": "not_installed",
            "tls_handshake_failures": 2,
            "tls_handshake_failures_by_host": {"api.demo.com": 2},
        }

    def get_capture_diagnostics(self):
        return {
            "cert": {
                "verification_status": "not_installed",
                "local_cert_exists": True,
                "device_cert_installed": False,
                "device_cert_store_accessible": True,
                "device_cert_checked_path": "/data/misc/user/0/cacerts-added/abcd1234.0",
                "device_download_cert_present": True,
                "local_cert_path": "~/.mitmproxy/mitmproxy-ca-cert.cer",
            },
            "tls": {
                "total_failures": 2,
                "by_host": {"api.demo.com": 2},
            },
        }


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


class _FakeTrafficMonitorNoNetwork(_FakeTrafficMonitor):
    def get_requests(self):
        return []

    def get_candidate_requests(self):
        return []

    def get_requests_as_dict(self):
        return []

    def get_candidate_requests_as_dict(self):
        return []

    def get_aggregated_requests(self):
        return []

    def get_candidate_aggregated_requests(self):
        return []

    def analyze_traffic(self):
        return {
            "total_requests": 0,
            "unique_hosts": 0,
            "sources": {},
            "candidate_total_requests": 0,
            "candidate_unique_hosts": 0,
            "candidate_sources": {},
            "cert_verification_status": "unknown",
            "tls_handshake_failures": 0,
            "tls_handshake_failures_by_host": {},
        }

    def get_capture_diagnostics(self):
        return {
            "cert": {
                "verification_status": "unknown",
                "local_cert_exists": False,
                "device_cert_installed": None,
                "device_cert_store_accessible": None,
                "device_cert_checked_path": None,
                "device_download_cert_present": False,
                "local_cert_path": "~/.mitmproxy/mitmproxy-ca-cert.cer",
            },
            "tls": {
                "total_failures": 0,
                "by_host": {},
            },
        }


class _FakeAppExplorerFail(_FakeAppExplorer):
    def run_full_exploration(self, emulator_config, apk_info, persist_screenshots="minio", local_screenshot_dir=None):
        shot = self.screenshot_manager.screenshots[0]
        if local_screenshot_dir:
            self.screenshot_manager.save_to_local(shot, local_screenshot_dir, 0)
        return ExplorationResult(
            total_steps=2,
            screenshots=self.screenshot_manager.get_all_for_report(),
            network_requests=[],
            activities_visited=["com.demo/.LoginActivity"],
            success=False,
            phases_completed=["setup"],
        )


def test_run_dynamic_analysis_minimal_writes_local_markdown(monkeypatch, tmp_path):
    apk_path = tmp_path / "sample.apk"
    apk_path.write_bytes(b"apk")

    monkeypatch.setattr(dynamic_analyzer, "AndroidRunner", _FakeAndroidRunner)
    monkeypatch.setattr(dynamic_analyzer, "TrafficMonitor", _FakeTrafficMonitor)
    monkeypatch.setattr(dynamic_analyzer, "AppExplorer", _FakeAppExplorer)
    monkeypatch.setattr(dynamic_analyzer, "MasterDomainAnalyzer", _FakeDomainAnalyzer)
    monkeypatch.setattr(dynamic_analyzer, "AIDriver", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(dynamic_analyzer, "_detect_package_name", lambda path: "com.demo.app")
    monkeypatch.setattr(
        dynamic_analyzer,
        "get_available_proxy_port",
        lambda task_id: {"node_name": "node-a", "port": 18080, "lease_token": "t1"},
    )
    monkeypatch.setattr(dynamic_analyzer, "release_proxy_port", lambda lease: None)

    result = dynamic_analyzer.run_dynamic_analysis_minimal(
        apk_path=str(apk_path),
        output_dir=str(tmp_path / "out"),
        max_steps=3,
    )

    report_path = Path(result["report_path"])
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "# 动态分析线索报告（最简增强版）" in text
    assert "com.demo.app" in text
    assert "api.demo.com" in text
    assert "edge.demo.com" in text
    assert result["status"] == "success"
    assert result["status_reason"] == "ok"
    assert result["combined_requests"] == 2
    assert result["cert_verification_status"] == "not_installed"
    assert result["tls_handshake_failures"] == 2
    assert "## 六、HTTPS 拦截诊断" in text
    assert "TLS 握手失败总数: `2`" in text


def test_run_dynamic_analysis_minimal_degraded_when_no_network(monkeypatch, tmp_path):
    apk_path = tmp_path / "sample.apk"
    apk_path.write_bytes(b"apk")

    monkeypatch.setattr(dynamic_analyzer, "AndroidRunner", _FakeAndroidRunner)
    monkeypatch.setattr(dynamic_analyzer, "TrafficMonitor", _FakeTrafficMonitorNoNetwork)
    monkeypatch.setattr(dynamic_analyzer, "AppExplorer", _FakeAppExplorer)
    monkeypatch.setattr(dynamic_analyzer, "MasterDomainAnalyzer", _FakeDomainAnalyzer)
    monkeypatch.setattr(dynamic_analyzer, "AIDriver", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(dynamic_analyzer, "_detect_package_name", lambda path: "com.demo.app")
    monkeypatch.setattr(
        dynamic_analyzer,
        "get_available_proxy_port",
        lambda task_id: {"node_name": "node-a", "port": 18080, "lease_token": "t1"},
    )
    monkeypatch.setattr(dynamic_analyzer, "release_proxy_port", lambda lease: None)

    result = dynamic_analyzer.run_dynamic_analysis_minimal(
        apk_path=str(apk_path),
        output_dir=str(tmp_path / "out_degraded"),
        max_steps=3,
    )

    assert result["status"] == "degraded_no_network"
    assert result["status_reason"] == "no_network_requests_captured"
    assert result["combined_requests"] == 0


def test_run_dynamic_analysis_minimal_failed_when_exploration_fails(monkeypatch, tmp_path):
    apk_path = tmp_path / "sample.apk"
    apk_path.write_bytes(b"apk")

    monkeypatch.setattr(dynamic_analyzer, "AndroidRunner", _FakeAndroidRunner)
    monkeypatch.setattr(dynamic_analyzer, "TrafficMonitor", _FakeTrafficMonitor)
    monkeypatch.setattr(dynamic_analyzer, "AppExplorer", _FakeAppExplorerFail)
    monkeypatch.setattr(dynamic_analyzer, "MasterDomainAnalyzer", _FakeDomainAnalyzer)
    monkeypatch.setattr(dynamic_analyzer, "AIDriver", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(dynamic_analyzer, "_detect_package_name", lambda path: "com.demo.app")
    monkeypatch.setattr(
        dynamic_analyzer,
        "get_available_proxy_port",
        lambda task_id: {"node_name": "node-a", "port": 18080, "lease_token": "t1"},
    )
    monkeypatch.setattr(dynamic_analyzer, "release_proxy_port", lambda lease: None)

    result = dynamic_analyzer.run_dynamic_analysis_minimal(
        apk_path=str(apk_path),
        output_dir=str(tmp_path / "out_failed"),
        max_steps=3,
    )

    assert result["status"] == "failed_exploration"
    assert result["status_reason"] == "exploration_failed"
    assert result["exploration_success"] is False


def test_detect_package_name_fallback_to_aapt(monkeypatch):
    """Package detection should fallback to aapt when androguard parser fails."""
    fake_misc = SimpleNamespace(
        AnalyzeAPK=lambda _: (_ for _ in ()).throw(RuntimeError("encrypted manifest"))
    )
    monkeypatch.setitem(sys.modules, "androguard.misc", fake_misc)

    completed = Mock()
    completed.stdout = "package: name='com.fallback.demo' versionCode='1'"
    completed.stderr = ""
    monkeypatch.setattr(dynamic_analyzer.subprocess, "run", lambda *args, **kwargs: completed)

    package = dynamic_analyzer._detect_package_name("/tmp/fake.apk")
    assert package == "com.fallback.demo"
