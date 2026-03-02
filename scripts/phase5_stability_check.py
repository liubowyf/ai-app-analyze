"""Run phase4 gate check repeatedly to verify short-window stability."""

from __future__ import annotations

import argparse
import json
from typing import Callable

from scripts.gate_config import load_gate_runtime_config
from scripts.phase4_gate_check import run_phase4_gate_check

GateRunner = Callable[..., tuple[int, dict[str, object]]]


def run_phase5_stability_check(
    runs: int = 3,
    window_minutes: int = 30,
    snapshot_prefix: str = "/tmp/phase5_gate_window",
    gate_runner: GateRunner = run_phase4_gate_check,
) -> tuple[int, dict[str, object]]:
    total_runs = max(1, int(runs))
    items: list[dict[str, object]] = []

    for index in range(1, total_runs + 1):
        snapshot_json = f"{snapshot_prefix}_{index}.json"
        code, report = gate_runner(snapshot_json=snapshot_json, window_minutes=window_minutes)
        action = str(report.get("final_action", "rollback_now"))
        reason = str(report.get("final_reason", "unknown"))
        items.append(
            {
                "run": index,
                "returncode": int(code),
                "snapshot_json": snapshot_json,
                "final_action": action,
                "final_reason": reason,
            }
        )

        if action != "continue":
            return 1, {
                "final_action": action,
                "final_reason": f"run_{index}:{reason}",
                "runs": items,
            }

    return 0, {
        "final_action": "continue",
        "final_reason": "all_runs_continue",
        "runs": items,
    }


def _build_parser() -> argparse.ArgumentParser:
    config = load_gate_runtime_config()
    parser = argparse.ArgumentParser(description="Run phase4 gate check repeatedly")
    parser.add_argument(
        "--runs",
        type=int,
        default=config.phase5_runs,
        help="How many consecutive gate runs to execute",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=config.window_minutes,
        help="Window size passed to phase4 gate",
    )
    parser.add_argument(
        "--snapshot-prefix",
        default="/tmp/phase5_gate_window",
        help="Snapshot prefix used for each run",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    code, report = run_phase5_stability_check(
        runs=args.runs,
        window_minutes=args.window_minutes,
        snapshot_prefix=args.snapshot_prefix,
    )
    print(f"final_action={report['final_action']}")
    print(f"final_reason={report['final_reason']}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
