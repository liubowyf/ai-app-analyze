"""Contract tests for phase4 gate check orchestrator."""

from __future__ import annotations

from scripts.phase4_gate_check import CommandResult, run_phase4_gate_check


def _fake_runner_factory(guard_output: str, guard_code: int, rollback_output: str, rollback_code: int):
    def _runner(cmd: list[str]) -> CommandResult:
        joined = " ".join(cmd)
        if "verify_collect_stability.py" in joined:
            return CommandResult(returncode=0, stdout="[PASS] collect", stderr="")
        if "pytest --collect-only -q" in joined:
            return CommandResult(returncode=0, stdout="343 tests collected", stderr="")
        if "scheduling_window_snapshot.py" in joined:
            return CommandResult(returncode=0, stdout="snapshot_ok", stderr="")
        if "rollout_guard.py" in joined:
            return CommandResult(returncode=guard_code, stdout=guard_output, stderr="")
        if "rollback_smoke.py" in joined:
            return CommandResult(returncode=rollback_code, stdout=rollback_output, stderr="")
        return CommandResult(returncode=1, stdout="", stderr=f"unexpected command: {joined}")

    return _runner


def test_gate_check_continue_path():
    runner = _fake_runner_factory(
        guard_output="action=continue\nreason=all_gates_passed\n",
        guard_code=0,
        rollback_output="rollback_ready=True\n",
        rollback_code=0,
    )

    code, report = run_phase4_gate_check(runner=runner)

    assert code == 0
    assert report["final_action"] == "continue"
    assert report["final_reason"] == "all_gates_passed"


def test_gate_check_hold_path():
    runner = _fake_runner_factory(
        guard_output="action=hold\nreason=insufficient_sample_size\n",
        guard_code=2,
        rollback_output="rollback_ready=True\n",
        rollback_code=0,
    )

    code, report = run_phase4_gate_check(runner=runner)

    assert code == 2
    assert report["final_action"] == "hold"
    assert report["final_reason"] == "insufficient_sample_size"


def test_gate_check_rollback_path():
    runner = _fake_runner_factory(
        guard_output="action=rollback_now\nreason=scheduling_stuck_tasks_detected\n",
        guard_code=1,
        rollback_output="rollback_ready=True\n",
        rollback_code=0,
    )

    code, report = run_phase4_gate_check(runner=runner)

    assert code == 1
    assert report["final_action"] == "rollback_now"
    assert report["final_reason"] == "scheduling_stuck_tasks_detected"


def test_gate_check_fails_when_rollback_smoke_not_ready():
    runner = _fake_runner_factory(
        guard_output="action=continue\nreason=all_gates_passed\n",
        guard_code=0,
        rollback_output="rollback_ready=False\n",
        rollback_code=0,
    )

    code, report = run_phase4_gate_check(runner=runner)

    assert code == 1
    assert report["final_action"] == "rollback_now"
    assert report["final_reason"] == "rollback_not_ready"
