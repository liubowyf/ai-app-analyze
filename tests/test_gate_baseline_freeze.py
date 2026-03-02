"""Baseline freeze contract tests for scheduling gate artifacts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.gate_config import load_gate_runtime_config
from scripts.phase4_gate_check import CommandResult, run_phase4_gate_check

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_gate_config_default_contract(monkeypatch):
    for key in (
        "GATE_COLLECT_TIMEOUT_SECONDS",
        "GATE_PHASE5_RUNS",
        "GATE_WINDOW_MINUTES",
        "GATE_MIN_SAMPLE",
    ):
        monkeypatch.delenv(key, raising=False)

    cfg = load_gate_runtime_config()

    assert cfg.collect_timeout_seconds == 30
    assert cfg.phase5_runs == 3
    assert cfg.window_minutes == 30
    assert cfg.guard_min_sample == 30


def test_phase4_gate_check_report_contains_final_contract_fields():
    def fake_runner(cmd: list[str]) -> CommandResult:
        joined = " ".join(cmd)
        if "verify_collect_stability.py" in joined:
            return CommandResult(returncode=0, stdout="[PASS] collect", stderr="")
        if "pytest --collect-only -q" in joined:
            return CommandResult(returncode=0, stdout="358 tests collected", stderr="")
        if "scheduling_window_snapshot.py" in joined:
            return CommandResult(returncode=0, stdout="snapshot_ok", stderr="")
        if "rollout_guard.py" in joined:
            return CommandResult(returncode=0, stdout="action=continue\nreason=all_gates_passed\n", stderr="")
        if "rollback_smoke.py" in joined:
            return CommandResult(returncode=0, stdout="rollback_ready=True\n", stderr="")
        return CommandResult(returncode=1, stdout="", stderr=f"unexpected command: {joined}")

    code, report = run_phase4_gate_check(runner=fake_runner)

    assert code == 0
    assert "final_action" in report
    assert "final_reason" in report
    assert report["final_action"] == "continue"
    assert report["final_reason"] == "all_gates_passed"


def test_ci_gate_entry_returns_non_zero_when_gate_command_fails():
    env = os.environ.copy()
    env["CI_GATE_COMMAND"] = (
        "python -c \"import sys;"
        "print('final_action=hold');"
        "print('final_reason=baseline_freeze_failure');"
        "sys.exit(9)\""
    )

    proc = subprocess.run(
        ["bash", "scripts/ci_gate_entry.sh"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 9
    assert "final_action=hold" in proc.stdout
    assert "final_reason=baseline_freeze_failure" in proc.stdout
