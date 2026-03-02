"""Phase 4 scheduling gate orchestration."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from typing import Callable

from scripts.gate_config import load_gate_runtime_config

@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str]], CommandResult]


def _default_runner(cmd: list[str]) -> CommandResult:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return CommandResult(returncode=proc.returncode, stdout=proc.stdout or "", stderr=proc.stderr or "")


def _run_shell(command: str, runner: Runner) -> CommandResult:
    return runner(["zsh", "-lc", command])


def _parse_guard(stdout: str) -> tuple[str, str]:
    action = ""
    reason = ""
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        if line.startswith("action="):
            action = line.split("=", 1)[1].strip()
        elif line.startswith("reason="):
            reason = line.split("=", 1)[1].strip()
    return action, reason


def _rollback_ready(stdout: str) -> bool:
    for raw in (stdout or "").splitlines():
        line = raw.strip().lower()
        if line.startswith("rollback_ready="):
            return line.endswith("true")
    return False


def run_phase4_gate_check(
    snapshot_json: str = "/tmp/phase4_gate_window.json",
    window_minutes: int | None = None,
    min_sample: int | None = None,
    runner: Runner = _default_runner,
) -> tuple[int, dict[str, object]]:
    config = load_gate_runtime_config()
    effective_window_minutes = int(window_minutes or config.window_minutes)
    effective_min_sample = int(min_sample or config.guard_min_sample)
    steps: list[dict[str, object]] = []

    command_specs = [
        (
            "verify_collect_stability",
            "PYTHONPATH=. ./venv/bin/python scripts/verify_collect_stability.py",
        ),
        (
            "pytest_collect_only",
            "PYTHONPATH=. ./venv/bin/pytest --collect-only -q",
        ),
        (
            "scheduling_window_snapshot",
            f"PYTHONPATH=. ./venv/bin/python scripts/scheduling_window_snapshot.py --minutes {effective_window_minutes} --output {snapshot_json}",
        ),
    ]

    for step_name, command in command_specs:
        result = _run_shell(command, runner)
        steps.append(
            {
                "name": step_name,
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode != 0:
            return 1, {
                "final_action": "rollback_now",
                "final_reason": f"step_failed:{step_name}",
                "steps": steps,
            }

    guard_command = (
        f"PYTHONPATH=. ./venv/bin/python scripts/rollout_guard.py "
        f"--snapshot-json {snapshot_json} --validation-mode scheduling "
        f"--min-sample {effective_min_sample}"
    )
    guard_result = _run_shell(guard_command, runner)
    guard_action, guard_reason = _parse_guard(guard_result.stdout)
    steps.append(
        {
            "name": "rollout_guard",
            "command": guard_command,
            "returncode": guard_result.returncode,
            "stdout": guard_result.stdout,
            "stderr": guard_result.stderr,
            "action": guard_action,
            "reason": guard_reason,
        }
    )

    if guard_action != "continue":
        if guard_action == "hold":
            return 2, {
                "final_action": "hold",
                "final_reason": guard_reason or "insufficient_sample_size",
                "steps": steps,
            }
        return 1, {
            "final_action": "rollback_now",
            "final_reason": guard_reason or "guard_failed",
            "steps": steps,
        }

    rollback_command = "PYTHONPATH=. ./venv/bin/python scripts/rollback_smoke.py"
    rollback_result = _run_shell(rollback_command, runner)
    ready = _rollback_ready(rollback_result.stdout)
    steps.append(
        {
            "name": "rollback_smoke",
            "command": rollback_command,
            "returncode": rollback_result.returncode,
            "stdout": rollback_result.stdout,
            "stderr": rollback_result.stderr,
            "rollback_ready": ready,
        }
    )

    if rollback_result.returncode != 0:
        return 1, {
            "final_action": "rollback_now",
            "final_reason": "rollback_smoke_failed",
            "steps": steps,
        }

    if not ready:
        return 1, {
            "final_action": "rollback_now",
            "final_reason": "rollback_not_ready",
            "steps": steps,
        }

    return 0, {
        "final_action": "continue",
        "final_reason": "all_gates_passed",
        "steps": steps,
    }


def _build_parser() -> argparse.ArgumentParser:
    config = load_gate_runtime_config()
    parser = argparse.ArgumentParser(description="Run Phase 4 scheduling gate checks")
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=config.window_minutes,
        help="Window size for scheduling snapshot",
    )
    parser.add_argument(
        "--min-sample",
        type=int,
        default=config.guard_min_sample,
        help="Minimum sample size required by rollout guard",
    )
    parser.add_argument("--snapshot-json", default="/tmp/phase4_gate_window.json", help="Snapshot output path")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    code, report = run_phase4_gate_check(
        snapshot_json=args.snapshot_json,
        window_minutes=args.window_minutes,
        min_sample=args.min_sample,
    )
    print(f"final_action={report['final_action']}")
    print(f"final_reason={report['final_reason']}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
