"""Integration tests for CI gate entry wiring."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_ci_gate_with_command(command: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CI_GATE_COMMAND"] = command
    return subprocess.run(
        ["bash", "scripts/ci_gate_entry.sh"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_ci_workflow_invokes_ci_gate_entry_script():
    workflow_path = REPO_ROOT / ".github" / "workflows" / "phase6-gate.yml"
    assert workflow_path.exists(), "CI workflow for gate is missing"

    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "scripts/ci_gate_entry.sh" in workflow_text


def test_ci_gate_entry_propagates_non_zero_and_final_fields():
    cmd = (
        "python -c \"import sys;"
        "print('final_action=hold');"
        "print('final_reason=unit_test_ci_mock');"
        "sys.exit(7)\""
    )
    proc = _run_ci_gate_with_command(cmd)

    assert proc.returncode == 7
    assert "final_action=hold" in proc.stdout
    assert "final_reason=unit_test_ci_mock" in proc.stdout


def test_ci_gate_entry_fails_when_final_fields_missing():
    cmd = "python -c \"print('hello')\""
    proc = _run_ci_gate_with_command(cmd)

    assert proc.returncode != 0
    assert "final_action=" in proc.stdout or "final_action=" in proc.stderr
