"""Daily scheduling-gate healthcheck with structured alert payload."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Callable

from scripts.gate_config import load_gate_runtime_config
from scripts.phase5_stability_check import run_phase5_stability_check

StabilityRunner = Callable[..., tuple[int, dict[str, object]]]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def run_daily_gate_healthcheck(
    runs: int = 3,
    window_minutes: int = 30,
    snapshot_prefix: str = "/tmp/daily_gate_window",
    stability_runner: StabilityRunner = run_phase5_stability_check,
) -> tuple[int, dict[str, object]]:
    timestamp = _utc_now_iso()
    code, phase5_report = stability_runner(
        runs=runs,
        window_minutes=window_minutes,
        snapshot_prefix=snapshot_prefix,
    )

    final_action = str(phase5_report.get("final_action", "rollback_now"))
    final_reason = str(phase5_report.get("final_reason", "unknown"))

    base_report: dict[str, object] = {
        "timestamp": timestamp,
        "runs_requested": int(runs),
        "window_minutes": int(window_minutes),
        "final_action": final_action,
        "final_reason": final_reason,
        "phase5_report": phase5_report,
    }

    if code == 0 and final_action == "continue":
        base_report["status"] = "healthy"
        return 0, base_report

    alert_payload = {
        "timestamp": timestamp,
        "action": final_action,
        "reason": final_reason,
        "source": "daily_gate_healthcheck",
    }
    base_report["status"] = "alert"
    base_report["alert_payload"] = alert_payload
    return 1, base_report


def _build_parser() -> argparse.ArgumentParser:
    config = load_gate_runtime_config()
    parser = argparse.ArgumentParser(description="Run daily scheduling gate healthcheck")
    parser.add_argument(
        "--runs",
        type=int,
        default=config.phase5_runs,
        help="How many phase4 gate runs to execute",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=config.window_minutes,
        help="Window size passed to phase4 gate",
    )
    parser.add_argument(
        "--snapshot-prefix",
        default="/tmp/daily_gate_window",
        help="Snapshot prefix used for phase5 runs",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    code, report = run_daily_gate_healthcheck(
        runs=args.runs,
        window_minutes=args.window_minutes,
        snapshot_prefix=args.snapshot_prefix,
    )
    print(f"status={report['status']}")
    print(f"final_action={report['final_action']}")
    print(f"final_reason={report['final_reason']}")
    if report["status"] == "alert":
        print(f"alert_payload={json.dumps(report['alert_payload'], ensure_ascii=False)}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
