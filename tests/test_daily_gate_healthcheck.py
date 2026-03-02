"""Tests for daily gate healthcheck script."""

from __future__ import annotations

from scripts.daily_gate_healthcheck import run_daily_gate_healthcheck


def test_daily_gate_healthcheck_success_path():
    def fake_phase5(*, runs: int, window_minutes: int, snapshot_prefix: str):
        return 0, {
            "final_action": "continue",
            "final_reason": "all_runs_continue",
            "runs": [{"run": 1, "final_action": "continue"}],
        }

    code, report = run_daily_gate_healthcheck(
        runs=3,
        window_minutes=30,
        snapshot_prefix="/tmp/daily_gate",
        stability_runner=fake_phase5,
    )

    assert code == 0
    assert report["status"] == "healthy"
    assert report["final_action"] == "continue"
    assert report["final_reason"] == "all_runs_continue"
    assert "timestamp" in report


def test_daily_gate_healthcheck_failure_emits_alert_payload():
    def fake_phase5(*, runs: int, window_minutes: int, snapshot_prefix: str):
        return 1, {
            "final_action": "hold",
            "final_reason": "run_1:insufficient_sample_size",
            "runs": [{"run": 1, "final_action": "hold"}],
        }

    code, report = run_daily_gate_healthcheck(
        runs=3,
        window_minutes=30,
        snapshot_prefix="/tmp/daily_gate",
        stability_runner=fake_phase5,
    )

    assert code == 1
    assert report["status"] == "alert"
    alert_payload = report["alert_payload"]
    assert alert_payload["action"] == "hold"
    assert alert_payload["reason"] == "run_1:insufficient_sample_size"
    assert "timestamp" in alert_payload
