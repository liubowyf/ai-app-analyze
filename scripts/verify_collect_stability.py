"""Verify pytest collection finishes within a bounded time."""

from __future__ import annotations

import os
import subprocess
import sys
import time

from scripts.gate_config import load_gate_runtime_config


def main() -> int:
    timeout_seconds = load_gate_runtime_config().collect_timeout_seconds
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
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
