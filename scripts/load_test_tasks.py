#!/usr/bin/env python3
"""Dispatch concurrent analysis tasks and generate load-test summary."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

from modules.task_orchestration.load_baseline import (
    build_worker_commands,
    count_configured_emulators,
    recommend_worker_baseline,
)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _upload_task(client: httpx.Client, api_base: str, apk_path: str) -> str:
    with open(apk_path, "rb") as f:
        files = {
            "file": (Path(apk_path).name, f, "application/vnd.android.package-archive"),
        }
        resp = client.post(f"{api_base}/api/v1/apk/upload", files=files, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    return str(body["task_id"])


def _poll_task_status(
    client: httpx.Client,
    api_base: str,
    task_id: str,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> Dict[str, Any]:
    started = time.time()
    while True:
        resp = client.get(f"{api_base}/api/v1/tasks/{task_id}", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status in ("completed", "failed"):
            return {
                "task_id": task_id,
                "status": status,
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "error_message": data.get("error_message"),
                "elapsed_seconds": int(time.time() - started),
            }
        if time.time() - started > timeout_seconds:
            return {
                "task_id": task_id,
                "status": "timeout",
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "error_message": "poll_timeout",
                "elapsed_seconds": int(time.time() - started),
            }
        time.sleep(poll_interval_seconds)


def _render_markdown(
    baseline: Dict[str, int],
    worker_commands: List[str],
    task_results: List[Dict[str, Any]],
) -> str:
    total = len(task_results)
    completed = sum(1 for x in task_results if x.get("status") == "completed")
    failed = sum(1 for x in task_results if x.get("status") == "failed")
    timeout = sum(1 for x in task_results if x.get("status") == "timeout")
    avg_elapsed = int(sum(x.get("elapsed_seconds", 0) for x in task_results) / total) if total else 0

    lines = [
        "# 并发压测基线报告",
        "",
        f"- 生成时间: `{_now_iso()}`",
        f"- 模拟器数量: `{baseline['emulator_count']}`",
        f"- CPU 数量: `{baseline['cpu_count']}`",
        "",
        "## 推荐参数",
        "",
        f"- API workers: `{baseline['api_workers']}`",
        f"- Dynamic worker concurrency: `{baseline['dynamic_worker_concurrency']}`",
        f"- Static worker concurrency: `{baseline['static_worker_concurrency']}`",
        f"- Report worker concurrency: `{baseline['report_worker_concurrency']}`",
        "",
        "## 推荐启动命令",
        "",
    ]
    for cmd in worker_commands:
        lines.append(f"- `{cmd}`")

    lines.extend(
        [
            "",
            "## 压测结果",
            "",
            f"- 任务总数: `{total}`",
            f"- 完成: `{completed}`",
            f"- 失败: `{failed}`",
            f"- 超时: `{timeout}`",
            f"- 平均耗时(秒): `{avg_elapsed}`",
            "",
            "| task_id | status | elapsed_seconds | error_message |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in task_results:
        lines.append(
            f"| {row.get('task_id')} | {row.get('status')} | {row.get('elapsed_seconds', 0)} | {row.get('error_message') or ''} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Load test runner for task pipeline")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--apk-path", default="", help="APK path for dispatching tasks")
    parser.add_argument("--tasks", type=int, default=0, help="Number of tasks to dispatch")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--output-dir", default="", help="Output directory for summary artifacts")
    args = parser.parse_args()

    emulators = count_configured_emulators()
    baseline = recommend_worker_baseline(emulators)
    worker_commands = build_worker_commands(baseline)

    task_results: List[Dict[str, Any]] = []
    if args.tasks > 0:
        if not args.apk_path:
            raise ValueError("--apk-path is required when --tasks > 0")
        apk_file = Path(args.apk_path).expanduser().resolve()
        if not apk_file.exists():
            raise FileNotFoundError(f"APK not found: {apk_file}")

        with httpx.Client() as client:
            task_ids = [_upload_task(client, args.api_base, str(apk_file)) for _ in range(args.tasks)]
            for task_id in task_ids:
                task_results.append(
                    _poll_task_status(
                        client=client,
                        api_base=args.api_base,
                        task_id=task_id,
                        timeout_seconds=args.timeout_seconds,
                        poll_interval_seconds=args.poll_interval_seconds,
                    )
                )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else Path("artifacts/load_tests") / ts
    base_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "generated_at": _now_iso(),
        "baseline": baseline,
        "worker_commands": worker_commands,
        "task_results": task_results,
    }
    json_path = base_dir / "summary.json"
    md_path = base_dir / "recommendation.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(baseline, worker_commands, task_results), encoding="utf-8")

    print(json.dumps({"summary_json": str(json_path), "recommendation_md": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
