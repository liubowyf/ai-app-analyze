"""Presenter helpers for frontend task detail responses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.analysis_tables import (
    AnalysisRunTable,
    DynamicAnalysisTable,
    MasterDomainTable,
    NetworkRequestTable,
    ScreenshotTable,
    StaticAnalysisTable,
)
from models.task import Task, TaskStatus
from modules.android_permissions.catalog import (
    aggregate_permission_summary_from_runs,
    build_permission_details,
)
from modules.frontend_presenters.failure_reasons import present_failure_reason
from modules.frontend_presenters.statuses import present_task_status


RUN_PREVIEW_LIMIT = 5
DOMAIN_PREVIEW_LIMIT = 5
NETWORK_PREVIEW_LIMIT = 5
IP_PREVIEW_LIMIT = 5
SCREENSHOT_PREVIEW_LIMIT = 6


@dataclass
class FrontendTaskDetailScreenshotSource:
    """Resolved screenshot source for a frontend task detail image request."""

    storage_path: str | None = None
    image_base64: str | None = None
    content_type: str = "image/png"


@dataclass
class FrontendTaskDetailIconSource:
    """Resolved icon source for a frontend task detail icon request."""

    storage_path: str | None = None
    image_base64: str | None = None
    content_type: str = "image/png"


def _status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _isoformat(value: object) -> Optional[str]:
    return value.isoformat() if value else None


def _dynamic_result(task: Task) -> dict[str, Any]:
    return task.dynamic_analysis_result if isinstance(task.dynamic_analysis_result, dict) else {}


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except Exception:
            return value
    return value


def _normalize_source_types(value: Any) -> list[str]:
    parsed = _parse_jsonish(value)
    if parsed is None:
        return []
    if isinstance(parsed, dict):
        return sorted(str(key) for key in parsed.keys())
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _normalize_source_breakdown(value: Any) -> dict[str, int]:
    parsed = _parse_jsonish(value)
    if not isinstance(parsed, dict):
        return {}
    result: dict[str, int] = {}
    for key, raw_value in parsed.items():
        try:
            result[str(key)] = int(raw_value or 0)
        except Exception:
            continue
    return result


def _serialize_domain_preview_from_row(row: MasterDomainTable) -> dict[str, Any]:
    hit_count = int(getattr(row, "request_count", 0) or 0)
    return {
        "domain": row.domain,
        "ip": row.ip,
        "score": int(getattr(row, "confidence_score", 0) or 0),
        "confidence": row.confidence_level,
        "hit_count": hit_count,
        "request_count": hit_count,
        "post_count": int(getattr(row, "post_count", 0) or 0),
        "unique_ip_count": int(getattr(row, "unique_ip_count", 0) or (1 if row.ip else 0)),
        "source_types": _normalize_source_types(getattr(row, "source_types_json", None)),
        "first_seen_at": _isoformat(getattr(row, "first_seen_at", None)),
        "last_seen_at": _isoformat(getattr(row, "last_seen_at", None)),
    }


def _normalize_domain_preview_item(item: dict[str, Any], capture_mode: str | None) -> dict[str, Any]:
    hit_count = int(item.get("hit_count") or item.get("request_count") or 0)
    return {
        "domain": item.get("domain"),
        "ip": item.get("ip"),
        "score": int(item.get("score") or 0),
        "confidence": item.get("confidence"),
        "hit_count": hit_count,
        "request_count": hit_count,
        "post_count": int(item.get("post_count") or 0),
        "unique_ip_count": int(item.get("unique_ip_count") or 0),
        "source_types": _normalize_source_types(item.get("source_types") or item.get("source_types_json")),
        "first_seen_at": item.get("first_seen_at"),
        "last_seen_at": item.get("last_seen_at"),
        "capture_mode": item.get("capture_mode") or capture_mode or "redroid_zeek",
    }


def _fallback_domains_preview(dynamic_result: dict[str, Any]) -> list[dict[str, Any]]:
    capture_mode = dynamic_result.get("capture_mode")
    masters = dynamic_result.get("master_domains")
    rows: Any = None
    if isinstance(masters, dict):
        rows = masters.get("master_domains")
    elif isinstance(masters, list):
        rows = masters
    if not isinstance(rows, list):
        summary = dynamic_result.get("network_observation_summary")
        if isinstance(summary, dict):
            rows = summary.get("domain_stats")
    if not isinstance(rows, list):
        rows = dynamic_result.get("domain_stats")
    if not isinstance(rows, list):
        return []
    return [_normalize_domain_preview_item(item, capture_mode) for item in rows if isinstance(item, dict)]


def _serialize_observation_preview_from_row(row: NetworkRequestTable) -> dict[str, Any]:
    first_seen_at = getattr(row, "first_seen_at", None) or getattr(row, "request_time", None)
    last_seen_at = getattr(row, "last_seen_at", None) or getattr(row, "request_time", None)
    domain = getattr(row, "host", None)
    return {
        "id": row.id,
        "url": row.url,
        "method": row.method or "UNKNOWN",
        "domain": domain,
        "host": domain,
        "path": row.path,
        "ip": row.ip,
        "port": row.port,
        "scheme": row.scheme,
        "response_code": row.response_code,
        "request_time": _isoformat(first_seen_at),
        "first_seen_at": _isoformat(first_seen_at),
        "last_seen_at": _isoformat(last_seen_at),
        "hit_count": int(getattr(row, "hit_count", 0) or 1),
        "source_type": getattr(row, "source_type", None) or "unknown",
        "transport": getattr(row, "transport", None) or "unknown",
        "protocol": getattr(row, "protocol", None) or "unknown",
        "capture_mode": getattr(row, "capture_mode", None) or "redroid_zeek",
        "attribution_tier": getattr(row, "attribution_tier", None) or "primary",
    }


def _normalize_observation_preview_item(
    item: dict[str, Any],
    default_tier: str,
    capture_mode: str | None,
) -> dict[str, Any]:
    first_seen_at = item.get("first_seen_at") or item.get("request_time")
    last_seen_at = item.get("last_seen_at") or item.get("request_time") or first_seen_at
    domain = item.get("domain") or item.get("host")
    return {
        "id": item.get("id"),
        "url": item.get("url"),
        "method": item.get("method") or "UNKNOWN",
        "domain": domain,
        "host": domain,
        "path": item.get("path"),
        "ip": item.get("ip"),
        "port": item.get("port"),
        "scheme": item.get("scheme"),
        "response_code": item.get("response_code"),
        "request_time": first_seen_at,
        "first_seen_at": first_seen_at,
        "last_seen_at": last_seen_at,
        "hit_count": int(item.get("hit_count") or item.get("count") or 1),
        "source_type": item.get("source_type") or item.get("source") or "unknown",
        "transport": item.get("transport") or "unknown",
        "protocol": item.get("protocol") or "unknown",
        "capture_mode": item.get("capture_mode") or capture_mode or "redroid_zeek",
        "attribution_tier": item.get("attribution_tier") or default_tier,
    }


def _fallback_observations_preview(dynamic_result: dict[str, Any]) -> list[dict[str, Any]]:
    capture_mode = dynamic_result.get("capture_mode")
    items: list[dict[str, Any]] = []
    preview_sources = [
        ("primary_observations_preview", "primary"),
        ("candidate_observations_preview", "candidate"),
        ("suspicious_requests", "primary"),
        ("candidate_requests", "candidate"),
    ]
    for key, tier in preview_sources:
        rows = dynamic_result.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                items.append(_normalize_observation_preview_item(row, tier, capture_mode))
    return items


def _build_source_breakdown(observations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in observations:
        source_type = str(row.get("source_type") or "unknown")
        counts[source_type] = counts.get(source_type, 0) + int(row.get("hit_count") or 0)
    return counts


def _merge_iso(current: str | None, candidate: str | None, *, choose_min: bool) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    return min(current, candidate) if choose_min else max(current, candidate)


def _build_ip_stats(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in observations:
        ip = row.get("ip")
        if not isinstance(ip, str) or not ip:
            continue

        entry = rows.setdefault(
            ip,
            {
                "ip": ip,
                "hit_count": 0,
                "domains": set(),
                "domain_hits": {},
                "source_types": set(),
                "first_seen_at": None,
                "last_seen_at": None,
            },
        )
        hit_count = int(row.get("hit_count") or 0)
        domain = row.get("domain") or row.get("host")
        if isinstance(domain, str) and domain:
            entry["domains"].add(domain)
            entry["domain_hits"][domain] = entry["domain_hits"].get(domain, 0) + hit_count

        entry["hit_count"] += hit_count
        entry["source_types"].add(str(row.get("source_type") or "unknown"))
        entry["first_seen_at"] = _merge_iso(
            entry["first_seen_at"],
            row.get("first_seen_at"),
            choose_min=True,
        )
        entry["last_seen_at"] = _merge_iso(
            entry["last_seen_at"],
            row.get("last_seen_at"),
            choose_min=False,
        )

    items: list[dict[str, Any]] = []
    for row in rows.values():
        domain_hits = row["domain_hits"]
        primary_domain = None
        if domain_hits:
            primary_domain = sorted(domain_hits.items(), key=lambda item: (-item[1], item[0]))[0][0]
        items.append(
            {
                "ip": row["ip"],
                "hit_count": int(row["hit_count"] or 0),
                "domain_count": len(row["domains"]),
                "primary_domain": primary_domain,
                "source_types": sorted(str(item) for item in row["source_types"]),
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
            }
        )

    items.sort(
        key=lambda item: (
            -int(item.get("hit_count") or 0),
            item.get("last_seen_at") or "",
            item.get("ip") or "",
        )
    )
    return items


def _build_ip_stats_from_domains(domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in domains:
        ip = row.get("ip")
        if not isinstance(ip, str) or not ip:
            continue

        entry = rows.setdefault(
            ip,
            {
                "ip": ip,
                "hit_count": 0,
                "domains": set(),
                "source_types": set(),
                "first_seen_at": None,
                "last_seen_at": None,
            },
        )
        domain = row.get("domain")
        if isinstance(domain, str) and domain:
            entry["domains"].add(domain)
        entry["hit_count"] += int(row.get("hit_count") or row.get("request_count") or 0)
        entry["source_types"].update(str(item) for item in row.get("source_types") or [])
        entry["first_seen_at"] = _merge_iso(
            entry["first_seen_at"],
            row.get("first_seen_at"),
            choose_min=True,
        )
        entry["last_seen_at"] = _merge_iso(
            entry["last_seen_at"],
            row.get("last_seen_at"),
            choose_min=False,
        )

    items = [
        {
            "ip": row["ip"],
            "hit_count": int(row["hit_count"] or 0),
            "domain_count": len(row["domains"]),
            "primary_domain": sorted(row["domains"])[0] if row["domains"] else None,
            "source_types": sorted(str(item) for item in row["source_types"]),
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
        }
        for row in rows.values()
    ]
    items.sort(
        key=lambda item: (
            -int(item.get("hit_count") or 0),
            item.get("last_seen_at") or "",
            item.get("ip") or "",
        )
    )
    return items


def _report_ready(status: object) -> bool:
    return _status_value(status) == TaskStatus.COMPLETED.value


def _retryable(status: object) -> bool:
    return bool(_status_value(status))


def _legacy_basic_info(task: Task) -> dict[str, Any]:
    static_result = task.static_analysis_result if isinstance(task.static_analysis_result, dict) else {}
    basic_info = static_result.get("basic_info")
    if isinstance(basic_info, dict):
        return basic_info
    return static_result


def _declared_permissions(task: Task) -> list[str]:
    static_result = task.static_analysis_result if isinstance(task.static_analysis_result, dict) else {}
    permissions = static_result.get("permissions")
    if not isinstance(permissions, list):
        return []

    names: list[str] = []
    for item in permissions:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        elif isinstance(item, str) and item:
            names.append(item)
    return names


def _static_info(task: Task, static_row: StaticAnalysisTable | None, dynamic_row: DynamicAnalysisTable | None) -> dict[str, Any]:
    basic_info = _legacy_basic_info(task)
    icon_path = basic_info.get("icon_storage_path")
    icon_url = f"/api/v1/frontend/tasks/{task.id}/icon" if isinstance(icon_path, str) and icon_path else None
    return {
        "app_name": _app_name(task, static_row, dynamic_row),
        "package_name": _package_name(task, static_row, dynamic_row),
        "version_name": basic_info.get("version_name"),
        "version_code": basic_info.get("version_code"),
        "min_sdk": basic_info.get("min_sdk"),
        "target_sdk": basic_info.get("target_sdk"),
        "apk_file_size": int(task.apk_file_size),
        "apk_md5": task.apk_md5,
        "declared_permissions": _declared_permissions(task),
        "icon_url": icon_url,
    }


def _package_name(
    task: Task,
    static_row: StaticAnalysisTable | None,
    dynamic_row: DynamicAnalysisTable | None,
) -> Optional[str]:
    if static_row and static_row.package_name:
        return static_row.package_name
    if dynamic_row and dynamic_row.detected_package:
        return dynamic_row.detected_package

    package_name = _legacy_basic_info(task).get("package_name")
    return package_name if isinstance(package_name, str) and package_name else None


def _app_name(task: Task, static_row: StaticAnalysisTable | None, dynamic_row: DynamicAnalysisTable | None) -> str:
    if static_row and static_row.app_name:
        return static_row.app_name

    app_name = _legacy_basic_info(task).get("app_name")
    if isinstance(app_name, str) and app_name:
        return app_name

    package_name = _package_name(task, static_row, dynamic_row)
    if package_name:
        return package_name.rsplit(".", 1)[-1]

    return task.apk_file_name.rsplit(".", 1)[0]


def _screenshot_image_url(task_id: str, screenshot: ScreenshotTable) -> str | None:
    if not screenshot.storage_path:
        return None
    return f"/api/v1/frontend/tasks/{task_id}/screenshots/{screenshot.id}"


def _risk_level(
    static_row: StaticAnalysisTable | None,
    dynamic_row: DynamicAnalysisTable | None,
    observation_hits: int = 0,
    master_domain_count: int = 0,
) -> str:
    static_risk = (getattr(static_row, "risk_level", "") or "").strip().lower()
    master_domains = int(getattr(dynamic_row, "master_domains", 0) or master_domain_count or 0)
    total_observations = int(
        getattr(dynamic_row, "total_observations", 0)
        or observation_hits
        or getattr(dynamic_row, "total_requests", 0)
        or 0
    )

    if static_risk in {"critical", "high"}:
        return "high"
    if static_risk == "medium":
        return "medium"
    if static_risk == "low":
        return "low"
    if master_domains >= 2:
        return "high"
    if master_domains >= 1 or total_observations > 20:
        return "medium"
    if total_observations > 0:
        return "low"
    return "unknown"


def build_frontend_task_detail(db: Session, task_id: str) -> dict[str, Any] | None:
    """Build a frontend-friendly task detail DTO."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    dynamic_result = _dynamic_result(task)
    static_row = db.query(StaticAnalysisTable).filter(StaticAnalysisTable.task_id == task_id).first()
    dynamic_row = db.query(DynamicAnalysisTable).filter(DynamicAnalysisTable.task_id == task_id).first()

    runs = (
        db.query(AnalysisRunTable)
        .filter(AnalysisRunTable.task_id == task_id)
        .order_by(AnalysisRunTable.started_at.desc(), AnalysisRunTable.attempt.desc(), AnalysisRunTable.id.desc())
        .all()
    )

    domains_query = db.query(MasterDomainTable).filter(MasterDomainTable.task_id == task_id)
    domain_rows = (
        domains_query
        .order_by(
            MasterDomainTable.confidence_score.desc(),
            MasterDomainTable.request_count.desc(),
            MasterDomainTable.id.desc(),
        )
        .all()
    )
    domain_preview_rows = [_serialize_domain_preview_from_row(row) for row in domain_rows]
    if not domain_preview_rows:
        domain_preview_rows = _fallback_domains_preview(dynamic_result)

    network_query = db.query(NetworkRequestTable).filter(NetworkRequestTable.task_id == task_id)
    network_requests = (
        network_query
        .order_by(
            NetworkRequestTable.last_seen_at.desc(),
            NetworkRequestTable.request_time.desc(),
            NetworkRequestTable.id.desc(),
        )
        .all()
    )
    observation_preview_rows = [_serialize_observation_preview_from_row(row) for row in network_requests]
    if not observation_preview_rows:
        observation_preview_rows = _fallback_observations_preview(dynamic_result)

    screenshots_query = db.query(ScreenshotTable).filter(ScreenshotTable.task_id == task_id)
    screenshots = (
        screenshots_query
        .order_by(ScreenshotTable.captured_at.desc(), ScreenshotTable.id.desc())
        .limit(SCREENSHOT_PREVIEW_LIMIT)
        .all()
    )

    stage_summary_map: dict[str, dict[str, Any]] = {}
    for row in runs:
        entry = stage_summary_map.setdefault(
            row.stage,
            {
                "stage": row.stage,
                "runs": 0,
                "success_runs": 0,
                "failed_runs": 0,
                "latest_status": row.status,
                "total_duration_seconds": 0,
            },
        )
        entry["runs"] += 1
        entry["total_duration_seconds"] += int(row.duration_seconds or 0)
        if row.status == "success":
            entry["success_runs"] += 1
        elif row.status == "failed":
            entry["failed_runs"] += 1

    errors: list[dict[str, Any]] = []
    if task.error_message:
        errors.append(
            {
                "source": "task",
                "stage": None,
                "message": present_failure_reason(task.error_message),
            }
        )
    for row in runs:
        if row.error_message:
            errors.append(
                {
                    "source": "run",
                    "stage": row.stage,
                    "message": present_failure_reason(row.error_message),
                }
            )

    status = present_task_status(task.status, getattr(task, "last_success_stage", None))
    report_ready = _report_ready(status)
    observation_summary = (
        dynamic_result.get("network_observation_summary")
        if isinstance(dynamic_result.get("network_observation_summary"), dict)
        else {}
    )
    source_breakdown = _normalize_source_breakdown(getattr(dynamic_row, "source_breakdown", None))
    if not source_breakdown:
        source_breakdown = _normalize_source_breakdown(observation_summary.get("source_breakdown"))
    if not source_breakdown:
        source_breakdown = _build_source_breakdown(observation_preview_rows)

    observation_hits = int(getattr(dynamic_row, "total_observations", 0) or 0)
    if observation_hits <= 0:
        observation_hits = int(observation_summary.get("total_observations") or observation_summary.get("total_requests") or 0)
    if observation_hits <= 0:
        observation_hits = sum(int(item.get("hit_count") or 0) for item in observation_preview_rows)
    if observation_hits <= 0:
        observation_hits = int(getattr(dynamic_row, "total_requests", 0) or 0)

    domains_count = int(getattr(dynamic_row, "unique_domains", 0) or observation_summary.get("unique_domains") or 0)
    domains_count = max(domains_count, len(domain_preview_rows))

    ips_count = int(getattr(dynamic_row, "unique_ips", 0) or observation_summary.get("unique_ips") or 0)
    if ips_count <= 0:
        ips_count = len({item["ip"] for item in observation_preview_rows if item.get("ip")})

    capture_mode = getattr(dynamic_row, "capture_mode", None) or dynamic_result.get("capture_mode")
    if not capture_mode and (observation_preview_rows or domain_preview_rows or source_breakdown):
        capture_mode = "redroid_zeek"

    network_requests_count = len(network_requests) if network_requests else len(observation_preview_rows)
    domains_preview = domain_preview_rows[:DOMAIN_PREVIEW_LIMIT]
    observations_preview = observation_preview_rows[:NETWORK_PREVIEW_LIMIT]
    ip_stats_preview = _build_ip_stats(observation_preview_rows)
    if not ip_stats_preview:
        ip_stats_preview = _build_ip_stats_from_domains(domain_preview_rows)
    permission_summary = aggregate_permission_summary_from_runs(runs)
    permission_details = build_permission_details(
        db,
        set(_declared_permissions(task))
        | set(permission_summary["requested_permissions"])
        | set(permission_summary["granted_permissions"])
        | set(permission_summary["failed_permissions"]),
    )

    return {
        "task": {
            "id": task.id,
            "app_name": _app_name(task, static_row, dynamic_row),
            "package_name": _package_name(task, static_row, dynamic_row),
            "apk_file_name": task.apk_file_name,
            "apk_file_size": int(task.apk_file_size),
            "apk_md5": task.apk_md5,
            "status": status,
            "risk_level": _risk_level(
                static_row,
                dynamic_row,
                observation_hits=observation_hits,
                master_domain_count=len(domain_preview_rows),
            ),
            "created_at": _isoformat(task.created_at),
            "started_at": _isoformat(task.started_at),
            "completed_at": _isoformat(task.completed_at),
            "error_message": present_failure_reason(task.error_message),
            "retry_count": int(task.retry_count or 0),
        },
        "static_info": _static_info(task, static_row, dynamic_row),
        "permission_summary": permission_summary,
        "permission_details": permission_details,
        "stage_summary": list(stage_summary_map.values()),
        "evidence_summary": {
            "runs_count": len(runs),
            "domains_count": domains_count,
            "ips_count": ips_count,
            "observation_hits": observation_hits,
            "network_requests_count": network_requests_count,
            "screenshots_count": screenshots_query.count(),
            "source_breakdown": source_breakdown,
            "capture_mode": capture_mode,
        },
        "runs_preview": [
            {
                "id": row.id,
                "stage": row.stage,
                "attempt": row.attempt,
                "status": row.status,
                "worker_name": row.worker_name,
                "emulator": row.emulator,
                "started_at": _isoformat(row.started_at),
                "completed_at": _isoformat(row.completed_at),
                "duration_seconds": int(row.duration_seconds or 0),
                "error_message": present_failure_reason(row.error_message),
            }
            for row in runs[:RUN_PREVIEW_LIMIT]
        ],
        "domains_preview": [
            row
            for row in domains_preview
        ],
        "ip_stats_preview": [
            row
            for row in ip_stats_preview[:IP_PREVIEW_LIMIT]
        ],
        "observations_preview": [
            row
            for row in observations_preview
        ],
        "screenshots_preview": [
            {
                "id": row.id,
                "storage_path": row.storage_path,
                "image_url": _screenshot_image_url(task.id, row),
                "file_size": int(row.file_size or 0),
                "stage": row.stage,
                "description": row.description,
                "captured_at": _isoformat(row.captured_at),
            }
            for row in screenshots
        ],
        "errors": errors,
        "retryable": _retryable(status),
        "report_ready": report_ready,
        "report_url": f"/reports/{task.id}" if report_ready else None,
    }


def resolve_frontend_task_detail_screenshot_source(
    db: Session,
    task_id: str,
    screenshot_ref: str,
) -> FrontendTaskDetailScreenshotSource | None:
    """Resolve a screenshot reference to storage or inline bytes for task detail image requests."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    row = (
        db.query(ScreenshotTable)
        .filter(ScreenshotTable.task_id == task_id, ScreenshotTable.id == screenshot_ref)
        .first()
    )
    if row and row.storage_path:
        return FrontendTaskDetailScreenshotSource(storage_path=row.storage_path)

    return None


def resolve_frontend_task_icon_source(
    db: Session,
    task_id: str,
) -> FrontendTaskDetailIconSource | None:
    """Resolve task icon source for frontend task detail icon requests."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    basic_info = _legacy_basic_info(task)
    storage_path = basic_info.get("icon_storage_path")
    if isinstance(storage_path, str) and storage_path:
        return FrontendTaskDetailIconSource(
            storage_path=storage_path,
            content_type=str(basic_info.get("icon_content_type") or "image/png"),
        )

    return None
