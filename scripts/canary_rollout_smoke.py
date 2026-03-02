"""Non-destructive canary rollout readiness smoke checks."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from math import ceil
from typing import Any

from modules.task_orchestration.queue_backend import get_backend_runtime_diagnostics


def _actor_path_available() -> bool:
    try:
        from workers.task_actor import run_task

        return callable(getattr(run_task, "send", None))
    except Exception:
        return False


def _to_non_negative_int(value: object, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return default


def _to_non_negative_float(value: object, default: float = 0.0) -> float:
    try:
        return max(0.0, float(value))
    except Exception:
        return default


def evaluate_evidence_gate(
    runs_count: int,
    network_count: int,
    domains_count: int,
    report_img_count: int,
) -> tuple[bool, str]:
    """Evaluate canary evidence gate and return (pass, reason)."""
    if _to_non_negative_int(runs_count) <= 0:
        return False, "runs_empty"
    if _to_non_negative_int(network_count) <= 0:
        return False, "network_empty"
    if _to_non_negative_int(domains_count) <= 0:
        return False, "domains_empty"
    if _to_non_negative_int(report_img_count) <= 0:
        return False, "report_images_empty"
    return True, "evidence_ok"


def _read_evidence_counts(evidence_counts: dict[str, object] | None = None) -> dict[str, int]:
    if evidence_counts is None:
        evidence_counts = {
            "runs_count": os.getenv("CANARY_RUNS_COUNT", "0"),
            "network_count": os.getenv("CANARY_NETWORK_COUNT", "0"),
            "domains_count": os.getenv("CANARY_DOMAINS_COUNT", "0"),
            "report_img_count": os.getenv("CANARY_REPORT_IMG_COUNT", "0"),
        }
    return {
        "runs_count": _to_non_negative_int(evidence_counts.get("runs_count", 0)),
        "network_count": _to_non_negative_int(evidence_counts.get("network_count", 0)),
        "domains_count": _to_non_negative_int(evidence_counts.get("domains_count", 0)),
        "report_img_count": _to_non_negative_int(evidence_counts.get("report_img_count", 0)),
    }


def _extract_snapshot_tasks(snapshot_payload: object) -> list[dict[str, object]]:
    if isinstance(snapshot_payload, list):
        return [item for item in snapshot_payload if isinstance(item, dict)]
    if isinstance(snapshot_payload, dict):
        tasks = snapshot_payload.get("tasks")
        if isinstance(tasks, list):
            return [item for item in tasks if isinstance(item, dict)]
    return []


def _read_snapshot_payload(snapshot_json: str | None = None) -> dict[str, Any]:
    if snapshot_json:
        with open(snapshot_json, "r", encoding="utf-8") as f:
            payload = json.load(f)
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, list):
                return {"tasks": payload}
            return {}
    payload = os.getenv("CANARY_ROLLOUT_SNAPSHOT")
    if payload:
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"tasks": parsed}
    return {}


def build_rollout_summary(task_samples: list[dict[str, object]]) -> dict[str, object]:
    """Build structured rollout summary for observability and guard decisions."""
    total = len(task_samples)
    if total <= 0:
        return {
            "success_rate": 0.0,
            "p95_duration_seconds": 0,
            "evidence_completeness_rate": 0.0,
            "failed_reason_topN": [],
        }

    success_count = 0
    evidence_ok_count = 0
    durations: list[int] = []
    failure_reasons: Counter[str] = Counter()

    for sample in task_samples:
        status = str(sample.get("status", "")).strip().lower()
        if status in {"completed", "success"}:
            success_count += 1

        runs = _to_non_negative_int(sample.get("runs_count", sample.get("runs", 0)))
        network = _to_non_negative_int(sample.get("network_count", sample.get("network", 0)))
        domains = _to_non_negative_int(sample.get("domains_count", sample.get("domains", 0)))
        images = _to_non_negative_int(sample.get("report_img_count", sample.get("img_count", 0)))
        evidence_ok, evidence_reason = evaluate_evidence_gate(
            runs_count=runs,
            network_count=network,
            domains_count=domains,
            report_img_count=images,
        )
        if evidence_ok:
            evidence_ok_count += 1

        duration = _to_non_negative_int(sample.get("duration_seconds", 0))
        durations.append(duration)

        error_message = str(sample.get("error_message") or "").strip()
        if error_message:
            failure_reasons[error_message] += 1
        elif not evidence_ok:
            failure_reasons[evidence_reason] += 1

    durations.sort()
    p95_index = max(0, min(len(durations) - 1, ceil(len(durations) * 0.95) - 1))
    top_reasons = [
        {"reason": reason, "count": count}
        for reason, count in failure_reasons.most_common(5)
    ]
    return {
        "success_rate": round(success_count / total, 4),
        "p95_duration_seconds": durations[p95_index],
        "evidence_completeness_rate": round(evidence_ok_count / total, 4),
        "failed_reason_topN": top_reasons,
    }


def _derive_stuck_tasks(task_samples: list[dict[str, object]]) -> int:
    stuck = 0
    for sample in task_samples:
        if bool(sample.get("stuck", False)):
            stuck += 1
            continue
        status = str(sample.get("status", "")).strip().lower()
        if status in {"queued", "static_analyzing", "dynamic_analyzing", "report_generating", "retrying"}:
            stuck += 1
    return stuck


def _build_scheduling_summary(
    snapshot_payload: dict[str, Any] | None,
    task_samples: list[dict[str, object]],
) -> dict[str, object]:
    snapshot = snapshot_payload or {}
    rollout = build_rollout_summary(task_samples)
    return {
        "success_rate": _to_non_negative_float(
            snapshot.get("success_rate"),
            default=rollout["success_rate"],
        ),
        "stuck_tasks": _to_non_negative_int(
            snapshot.get("stuck_tasks"),
            default=_derive_stuck_tasks(task_samples),
        ),
        "retry_recovered_rate": _to_non_negative_float(
            snapshot.get("retry_recovered_rate"),
            default=1.0,
        ),
        "p95_queue_to_start_seconds": _to_non_negative_int(
            snapshot.get("p95_queue_to_start_seconds"),
            default=0,
        ),
        "failed_reason_topN": snapshot.get("failed_reason_topN") or rollout["failed_reason_topN"],
    }


def build_canary_readiness_report(
    evidence_counts: dict[str, object] | None = None,
    task_samples: list[dict[str, object]] | None = None,
    validation_mode: str = "scheduling",
    snapshot_payload: dict[str, Any] | None = None,
) -> dict[str, object]:
    diagnostics = get_backend_runtime_diagnostics()
    backend = str(diagnostics.get("backend", "dramatiq"))
    dramatiq_ready = bool(diagnostics.get("dramatiq_ready", False))
    fallback_reason = diagnostics.get("fallback_reason")
    can_enqueue = backend == "dramatiq" and dramatiq_ready
    actor_ok = _actor_path_available()
    counts = _read_evidence_counts(evidence_counts=evidence_counts)
    evidence_ok, evidence_reason = evaluate_evidence_gate(**counts)
    samples = task_samples or []
    if not samples:
        samples = [
            {
                "status": "completed" if evidence_ok else "failed",
                "duration_seconds": _to_non_negative_int(os.getenv("CANARY_DURATION_SECONDS", "0")),
                "runs_count": counts["runs_count"],
                "network_count": counts["network_count"],
                "domains_count": counts["domains_count"],
                "report_img_count": counts["report_img_count"],
                "error_message": None if evidence_ok else evidence_reason,
            }
        ]
    summary = build_rollout_summary(samples)
    scheduling_summary = _build_scheduling_summary(snapshot_payload=snapshot_payload, task_samples=samples)

    if not can_enqueue:
        go_no_go = "no-go"
        go_no_go_reason = "enqueue_not_ready"
    elif not actor_ok:
        go_no_go = "no-go"
        go_no_go_reason = "actor_path_unavailable"
    elif validation_mode == "scheduling" and scheduling_summary["stuck_tasks"] > 0:
        go_no_go = "no-go"
        go_no_go_reason = "scheduling_stuck_tasks_detected"
    elif validation_mode == "scheduling" and scheduling_summary["success_rate"] < 0.95:
        go_no_go = "no-go"
        go_no_go_reason = "scheduling_success_rate_low"
    elif validation_mode == "e2e" and not evidence_ok:
        go_no_go = "no-go"
        go_no_go_reason = evidence_reason
    elif validation_mode == "scheduling":
        go_no_go = "go"
        go_no_go_reason = "scheduling_ready"
    else:
        go_no_go = "go"
        go_no_go_reason = "ready"

    return {
        "backend": backend,
        "dramatiq_ready": dramatiq_ready,
        "fallback_reason": fallback_reason,
        "can_enqueue": can_enqueue,
        "actor_path_available": actor_ok,
        "runs_count": counts["runs_count"],
        "network_count": counts["network_count"],
        "domains_count": counts["domains_count"],
        "report_img_count": counts["report_img_count"],
        "go_no_go": go_no_go,
        "go_no_go_reason": go_no_go_reason,
        "success_rate": scheduling_summary["success_rate"] if validation_mode == "scheduling" else summary["success_rate"],
        "stuck_tasks": scheduling_summary["stuck_tasks"],
        "retry_recovered_rate": scheduling_summary["retry_recovered_rate"],
        "p95_queue_to_start_seconds": scheduling_summary["p95_queue_to_start_seconds"],
        "p95_duration_seconds": summary["p95_duration_seconds"],
        "evidence_completeness_rate": summary["evidence_completeness_rate"],
        "failed_reason_topN": scheduling_summary["failed_reason_topN"] if validation_mode == "scheduling" else summary["failed_reason_topN"],
        "validation_mode": validation_mode,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canary rollout readiness smoke checks")
    parser.add_argument(
        "--validation-mode",
        choices=("scheduling", "e2e"),
        default="scheduling",
        help="Validation gate mode (default: scheduling)",
    )
    parser.add_argument("--runs-count", type=int, help="Observed runs count")
    parser.add_argument("--network-count", type=int, help="Observed network request count")
    parser.add_argument("--domains-count", type=int, help="Observed domains count")
    parser.add_argument("--report-img-count", type=int, help="Observed report image count")
    parser.add_argument("--snapshot-json", help="Optional rollout snapshot json file with tasks[]")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    evidence_counts = None
    if any(
        value is not None
        for value in (args.runs_count, args.network_count, args.domains_count, args.report_img_count)
    ):
        evidence_counts = {
            "runs_count": args.runs_count or 0,
            "network_count": args.network_count or 0,
            "domains_count": args.domains_count or 0,
            "report_img_count": args.report_img_count or 0,
        }

    snapshot_payload = _read_snapshot_payload(args.snapshot_json)
    snapshot_tasks = _extract_snapshot_tasks(snapshot_payload)
    report = build_canary_readiness_report(
        evidence_counts=evidence_counts,
        task_samples=snapshot_tasks,
        validation_mode=args.validation_mode,
        snapshot_payload=snapshot_payload,
    )
    print("=== Canary Rollout Smoke ===")
    print(f"backend={report['backend']}")
    print(f"dramatiq_ready={report['dramatiq_ready']}")
    print(f"fallback_reason={report['fallback_reason']}")
    print(f"can_enqueue={report['can_enqueue']}")
    print(f"actor_path_available={report['actor_path_available']}")
    print(f"runs_count={report['runs_count']}")
    print(f"network_count={report['network_count']}")
    print(f"domains_count={report['domains_count']}")
    print(f"report_img_count={report['report_img_count']}")
    print(f"go_no_go={report['go_no_go']}")
    print(f"go_no_go_reason={report['go_no_go_reason']}")
    print(f"validation_mode={report['validation_mode']}")
    print(f"success_rate={report['success_rate']}")
    print(f"stuck_tasks={report['stuck_tasks']}")
    print(f"retry_recovered_rate={report['retry_recovered_rate']}")
    print(f"p95_queue_to_start_seconds={report['p95_queue_to_start_seconds']}")
    print(f"p95_duration_seconds={report['p95_duration_seconds']}")
    print(f"evidence_completeness_rate={report['evidence_completeness_rate']}")
    print(f"failed_reason_topN={json.dumps(report['failed_reason_topN'], ensure_ascii=False)}")
    return 0 if report["go_no_go"] == "go" else 1


if __name__ == "__main__":
    raise SystemExit(main())
