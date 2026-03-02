"""Tests for canary/rollback smoke script gates."""

from scripts.canary_rollout_smoke import evaluate_evidence_gate


def test_evaluate_evidence_gate_rejects_empty_runs():
    ok, reason = evaluate_evidence_gate(
        runs_count=0,
        network_count=10,
        domains_count=3,
        report_img_count=4,
    )

    assert ok is False
    assert reason == "runs_empty"


def test_evaluate_evidence_gate_accepts_non_empty_evidence():
    ok, reason = evaluate_evidence_gate(
        runs_count=3,
        network_count=10,
        domains_count=3,
        report_img_count=4,
    )

    assert ok is True
    assert reason == "evidence_ok"
