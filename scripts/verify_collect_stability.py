"""Verify pytest collection finishes within a bounded time."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time

DEFAULT_COLLECT_TARGETS = [
    "tests/test_redroid_remote_backend.py",
    "tests/test_redroid_ssh_client.py",
    "tests/test_redroid_device_controller.py",
    "tests/test_redroid_traffic_collector.py",
    "tests/test_redroid_traffic_parser.py",
    "tests/test_dynamic_analyzer_backend_switch.py",
    "tests/test_android_runner_enhanced.py",
    "tests/test_config.py",
    "tests/test_stage_services.py",
    "tests/test_task_actor_state_machine_runtime.py",
]


def main() -> int:
    timeout_seconds = int(os.getenv("COLLECT_TIMEOUT_SECONDS", "30"))
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    target_args = os.getenv("PYTEST_COLLECT_TARGETS", "").strip()
    if target_args:
        cmd.extend(shlex.split(target_args))
    else:
        cmd.extend(DEFAULT_COLLECT_TARGETS)
    extra_args = os.getenv("PYTEST_COLLECT_EXTRA_ARGS", "").strip()
    if extra_args:
        cmd.extend(shlex.split(extra_args))
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", ".")

    start = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        print(f"[FAIL] collect timed out after {elapsed:.1f}s (limit={timeout_seconds}s)")
        return 1

    elapsed = time.monotonic() - start
    if completed.returncode != 0:
        print(f"[FAIL] collect exited non-zero ({completed.returncode}) in {elapsed:.1f}s")
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip())
        return completed.returncode

    print(f"[PASS] collect completed in {elapsed:.1f}s")
    if completed.stdout.strip():
        print(completed.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
