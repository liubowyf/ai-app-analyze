"""Tests for phase5 stability gate runner."""

from scripts.phase5_stability_check import run_phase5_stability_check


def test_phase5_stability_check_returns_continue_when_all_runs_continue():
    outcomes = [(0, {"final_action": "continue", "final_reason": "all_gates_passed"})] * 3
    calls = []

    def fake_gate(*, snapshot_json: str, window_minutes: int):
        calls.append((snapshot_json, window_minutes))
        return outcomes[len(calls) - 1]

    code, report = run_phase5_stability_check(
        runs=3,
        window_minutes=30,
        snapshot_prefix="/tmp/test_phase5",
        gate_runner=fake_gate,
    )

    assert code == 0
    assert report["final_action"] == "continue"
    assert report["final_reason"] == "all_runs_continue"
    assert len(report["runs"]) == 3
    assert len(calls) == 3


def test_phase5_stability_check_fails_on_first_non_continue_result():
    outcomes = [
        (0, {"final_action": "continue", "final_reason": "all_gates_passed"}),
        (2, {"final_action": "hold", "final_reason": "insufficient_sample_size"}),
        (0, {"final_action": "continue", "final_reason": "all_gates_passed"}),
    ]
    calls = []

    def fake_gate(*, snapshot_json: str, window_minutes: int):
        calls.append((snapshot_json, window_minutes))
        return outcomes[len(calls) - 1]

    code, report = run_phase5_stability_check(
        runs=3,
        window_minutes=30,
        snapshot_prefix="/tmp/test_phase5",
        gate_runner=fake_gate,
    )

    assert code == 1
    assert report["final_action"] == "hold"
    assert report["final_reason"] == "run_2:insufficient_sample_size"
    assert len(report["runs"]) == 2
    assert len(calls) == 2
