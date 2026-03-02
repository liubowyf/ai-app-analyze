"""Tests for canary scheduling-validation mode."""

from unittest.mock import patch

from scripts.canary_rollout_smoke import build_canary_readiness_report


@patch(
    "scripts.canary_rollout_smoke.get_backend_runtime_diagnostics",
    return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
)
@patch("scripts.canary_rollout_smoke._actor_path_available", return_value=True)
def test_scheduling_mode_can_go_without_e2e_evidence(_mock_actor, _mock_diag):
    report = build_canary_readiness_report(
        validation_mode="scheduling",
        snapshot_payload={
            "success_rate": 0.98,
            "stuck_tasks": 0,
            "retry_recovered_rate": 1.0,
            "p95_queue_to_start_seconds": 22,
        },
        evidence_counts={
            "runs_count": 0,
            "network_count": 0,
            "domains_count": 0,
            "report_img_count": 0,
        },
    )

    assert report["go_no_go"] == "go"
    assert report["go_no_go_reason"] == "scheduling_ready"
    assert report["backend"] == "dramatiq"
    assert report["can_enqueue"] is True
    assert report["success_rate"] == 0.98
    assert report["stuck_tasks"] == 0
    assert report["retry_recovered_rate"] == 1.0
    assert report["p95_queue_to_start_seconds"] == 22


@patch(
    "scripts.canary_rollout_smoke.get_backend_runtime_diagnostics",
    return_value={"backend": "dramatiq", "dramatiq_ready": True, "fallback_reason": None},
)
@patch("scripts.canary_rollout_smoke._actor_path_available", return_value=True)
def test_scheduling_mode_returns_stable_failure_reason_when_stuck(_mock_actor, _mock_diag):
    report = build_canary_readiness_report(
        validation_mode="scheduling",
        snapshot_payload={
            "success_rate": 1.0,
            "stuck_tasks": 2,
            "retry_recovered_rate": 1.0,
            "p95_queue_to_start_seconds": 40,
        },
    )

    assert report["go_no_go"] == "no-go"
    assert report["go_no_go_reason"] == "scheduling_stuck_tasks_detected"
