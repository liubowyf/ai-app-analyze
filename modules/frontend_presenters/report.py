"""Presenter helpers for frontend report responses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.analysis_tables import (
    DynamicAnalysisTable,
    MasterDomainTable,
    NetworkRequestTable,
    ScreenshotTable,
    StaticAnalysisTable,
)
from models.task import Task, TaskStatus


TOP_DOMAIN_LIMIT = 10
TOP_IP_LIMIT = 10
TIMELINE_LIMIT = 12


@dataclass
class FrontendReportScreenshotSource:
    """Resolved screenshot source for a frontend report image request."""

    storage_path: str | None = None
    image_base64: str | None = None
    content_type: str = "image/png"


@dataclass
class FrontendReportIconSource:
    """Resolved icon source for a frontend report icon request."""

    storage_path: str | None = None
    image_base64: str | None = None
    content_type: str = "image/png"


def _status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _isoformat(value: object) -> Optional[str]:
    return value.isoformat() if value else None


def _task_or_404(db: Session, task_id: str) -> Task | None:
    return db.query(Task).filter(Task.id == task_id).first()


def _ensure_completed(task: Task) -> None:
    if _status_value(task.status) != TaskStatus.COMPLETED.value:
        raise ValueError("Task not completed yet")


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
        return sorted(str(item) for item in parsed)
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


def _merge_iso(current: str | None, candidate: str | None, *, choose_min: bool) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    return min(current, candidate) if choose_min else max(current, candidate)


def _package_name(
    static_row: StaticAnalysisTable | None,
    dynamic_row: DynamicAnalysisTable | None,
    static_result: dict[str, Any],
) -> Optional[str]:
    if static_row and static_row.package_name:
        return static_row.package_name
    if dynamic_row and dynamic_row.detected_package:
        return dynamic_row.detected_package
    basic_info = static_result.get("basic_info") if isinstance(static_result.get("basic_info"), dict) else {}
    package_name = basic_info.get("package_name") or static_result.get("package_name")
    return package_name if isinstance(package_name, str) and package_name else None


def _app_name(
    task: Task,
    static_row: StaticAnalysisTable | None,
    dynamic_row: DynamicAnalysisTable | None,
    static_result: dict[str, Any],
) -> str:
    if static_row and static_row.app_name:
        return static_row.app_name

    basic_info = static_result.get("basic_info") if isinstance(static_result.get("basic_info"), dict) else {}
    app_name = basic_info.get("app_name") or static_result.get("app_name")
    if isinstance(app_name, str) and app_name:
        return app_name

    package_name = _package_name(static_row, dynamic_row, static_result)
    if package_name:
        return package_name.rsplit(".", 1)[-1]

    return task.apk_file_name.rsplit(".", 1)[0]


def _risk_level(
    static_row: StaticAnalysisTable | None,
    dynamic_row: DynamicAnalysisTable | None,
    static_result: dict[str, Any],
    domain_count: int,
    observation_hits: int,
) -> str:
    static_risk = (
        (getattr(static_row, "risk_level", None) or static_result.get("risk_level") or "")
        .strip()
        .lower()
    )
    master_domains = int(getattr(dynamic_row, "master_domains", domain_count) or domain_count or 0)
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


def _risk_label(level: str) -> str:
    return {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险",
        "unknown": "待确认",
    }.get(level, "待确认")


def _legacy_static_result(task: Task) -> dict[str, Any]:
    return task.static_analysis_result if isinstance(task.static_analysis_result, dict) else {}


def _declared_permissions(task: Task) -> list[str]:
    static_result = _legacy_static_result(task)
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


def _permission_summary(dynamic_row: DynamicAnalysisTable | None, legacy_dynamic: dict[str, Any]) -> dict[str, list[str]]:
    summary = getattr(dynamic_row, "permission_summary", None)
    if not isinstance(summary, dict):
        summary = legacy_dynamic.get("permission_summary")
    if not isinstance(summary, dict):
        summary = {}
    return {
        "requested_permissions": sorted(str(item) for item in summary.get("requested_permissions") or [] if isinstance(item, str) and item),
        "granted_permissions": sorted(str(item) for item in summary.get("granted_permissions") or [] if isinstance(item, str) and item),
        "failed_permissions": sorted(str(item) for item in summary.get("failed_permissions") or [] if isinstance(item, str) and item),
    }


def _static_info(
    task: Task,
    static_row: StaticAnalysisTable | None,
    dynamic_row: DynamicAnalysisTable | None,
    legacy_static: dict[str, Any],
) -> dict[str, Any]:
    basic_info = legacy_static.get("basic_info") if isinstance(legacy_static.get("basic_info"), dict) else legacy_static
    icon_path = basic_info.get("icon_storage_path")
    icon_url = f"/api/v1/frontend/reports/{task.id}/icon" if isinstance(icon_path, str) and icon_path else None
    return {
        "app_name": _app_name(task, static_row, dynamic_row, legacy_static),
        "package_name": _package_name(static_row, dynamic_row, legacy_static),
        "version_name": basic_info.get("version_name"),
        "version_code": basic_info.get("version_code"),
        "min_sdk": basic_info.get("min_sdk"),
        "target_sdk": basic_info.get("target_sdk"),
        "apk_file_size": int(task.apk_file_size),
        "apk_md5": task.apk_md5,
        "declared_permissions": _declared_permissions(task),
        "icon_url": icon_url,
    }


def _legacy_dynamic_result(task: Task) -> dict[str, Any]:
    return task.dynamic_analysis_result if isinstance(task.dynamic_analysis_result, dict) else {}


def _serialize_domain_from_row(row: MasterDomainTable) -> dict[str, Any]:
    hit_count = int(getattr(row, "request_count", 0) or 0)
    return {
        "id": row.id,
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
        "capture_mode": getattr(row, "capture_mode", None) or "redroid_zeek",
    }


def _normalize_domain_item(item: dict[str, Any], *, fallback_id: str, capture_mode: str | None) -> dict[str, Any]:
    hit_count = int(item.get("hit_count") or item.get("request_count") or 0)
    return {
        "id": str(item.get("id") or fallback_id),
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


def _legacy_domains(dynamic_result: dict[str, Any], capture_mode: str | None) -> list[dict[str, Any]]:
    rows: Any = None
    master_domains = dynamic_result.get("master_domains")
    if isinstance(master_domains, dict):
        rows = master_domains.get("master_domains")
    elif isinstance(master_domains, list):
        rows = master_domains
    if not isinstance(rows, list):
        summary = dynamic_result.get("network_observation_summary")
        if isinstance(summary, dict):
            rows = summary.get("domain_stats")
    if not isinstance(rows, list):
        rows = dynamic_result.get("domain_stats")
    if not isinstance(rows, list):
        return []
    return [
        _normalize_domain_item(item, fallback_id=f"legacy-domain-{index}", capture_mode=capture_mode)
        for index, item in enumerate(rows)
        if isinstance(item, dict)
    ]


def _serialize_observation_from_row(row: NetworkRequestTable) -> dict[str, Any]:
    first_seen_at = getattr(row, "first_seen_at", None) or getattr(row, "request_time", None)
    last_seen_at = getattr(row, "last_seen_at", None) or getattr(row, "request_time", None)
    domain = getattr(row, "host", None)
    return {
        "id": row.id,
        "domain": domain,
        "host": domain,
        "ip": row.ip,
        "port": row.port,
        "source_type": getattr(row, "source_type", None) or "unknown",
        "transport": getattr(row, "transport", None) or "unknown",
        "protocol": getattr(row, "protocol", None) or "unknown",
        "hit_count": int(getattr(row, "hit_count", 0) or 1),
        "first_seen_at": _isoformat(first_seen_at),
        "last_seen_at": _isoformat(last_seen_at),
        "capture_mode": getattr(row, "capture_mode", None) or "redroid_zeek",
        "attribution_tier": getattr(row, "attribution_tier", None) or "primary",
    }


def _normalize_observation_item(
    item: dict[str, Any],
    *,
    fallback_id: str,
    default_tier: str,
    capture_mode: str | None,
) -> dict[str, Any]:
    first_seen_at = item.get("first_seen_at") or item.get("request_time")
    last_seen_at = item.get("last_seen_at") or item.get("request_time") or first_seen_at
    domain = item.get("domain") or item.get("host")
    return {
        "id": str(item.get("id") or fallback_id),
        "domain": domain,
        "host": domain,
        "ip": item.get("ip"),
        "port": item.get("port"),
        "source_type": item.get("source_type") or item.get("source") or "unknown",
        "transport": item.get("transport") or "unknown",
        "protocol": item.get("protocol") or "unknown",
        "hit_count": int(item.get("hit_count") or item.get("count") or 1),
        "first_seen_at": first_seen_at,
        "last_seen_at": last_seen_at,
        "capture_mode": item.get("capture_mode") or capture_mode or "redroid_zeek",
        "attribution_tier": item.get("attribution_tier") or default_tier,
    }


def _legacy_observations(dynamic_result: dict[str, Any], capture_mode: str | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    preview_sources = [
        ("primary_observations_preview", "primary"),
        ("candidate_observations_preview", "candidate"),
        ("suspicious_requests", "primary"),
        ("candidate_requests", "candidate"),
        ("network_requests", "primary"),
    ]
    for key, default_tier in preview_sources:
        rows = dynamic_result.get(key)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                items.append(
                    _normalize_observation_item(
                        row,
                        fallback_id=f"{key}-{index}",
                        default_tier=default_tier,
                        capture_mode=capture_mode,
                    )
                )
    return items


def _legacy_screenshots(dynamic_result: dict[str, Any]) -> list[dict[str, Any]]:
    exploration = dynamic_result.get("exploration_result")
    if isinstance(exploration, dict) and isinstance(exploration.get("screenshots"), list):
        return [row for row in exploration["screenshots"] if isinstance(row, dict)]

    screenshots = dynamic_result.get("screenshots")
    if isinstance(screenshots, list):
        return [row for row in screenshots if isinstance(row, dict)]

    return []


def _report_screenshot_image_url(task_id: str, screenshot_id: str, has_content: bool) -> str | None:
    if not has_content:
        return None
    return f"/api/v1/frontend/reports/{task_id}/screenshots/{screenshot_id}"


def _build_source_breakdown(observations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in observations:
        source_type = str(row.get("source_type") or "unknown")
        counts[source_type] = counts.get(source_type, 0) + int(row.get("hit_count") or 0)
    return counts


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


def build_frontend_report(
    db: Session,
    task_id: str,
    *,
    require_completed: bool = True,
) -> dict[str, Any] | None:
    """Build a frontend-friendly report DTO for one completed task."""
    task = _task_or_404(db, task_id)
    if not task:
        return None
    if require_completed:
        _ensure_completed(task)

    static_row = db.query(StaticAnalysisTable).filter(StaticAnalysisTable.task_id == task_id).first()
    dynamic_row = db.query(DynamicAnalysisTable).filter(DynamicAnalysisTable.task_id == task_id).first()

    legacy_static = _legacy_static_result(task)
    legacy_dynamic = _legacy_dynamic_result(task)
    capture_mode = getattr(dynamic_row, "capture_mode", None) or legacy_dynamic.get("capture_mode")

    domain_rows = (
        db.query(MasterDomainTable)
        .filter(MasterDomainTable.task_id == task_id)
        .order_by(
            MasterDomainTable.confidence_score.desc(),
            MasterDomainTable.request_count.desc(),
            MasterDomainTable.id.desc(),
        )
        .all()
    )
    observation_rows = (
        db.query(NetworkRequestTable)
        .filter(NetworkRequestTable.task_id == task_id)
        .order_by(
            NetworkRequestTable.last_seen_at.desc(),
            NetworkRequestTable.request_time.desc(),
            NetworkRequestTable.id.desc(),
        )
        .all()
    )
    screenshot_rows = (
        db.query(ScreenshotTable)
        .filter(ScreenshotTable.task_id == task_id)
        .order_by(ScreenshotTable.captured_at.desc(), ScreenshotTable.id.desc())
        .all()
    )

    top_domains = [_serialize_domain_from_row(row) for row in domain_rows]
    if not top_domains:
        top_domains = _legacy_domains(legacy_dynamic, capture_mode)

    observations = [_serialize_observation_from_row(row) for row in observation_rows]
    if not observations:
        observations = _legacy_observations(legacy_dynamic, capture_mode)
    observations.sort(
        key=lambda item: (
            item.get("last_seen_at") or "",
            int(item.get("hit_count") or 0),
            item.get("domain") or "",
            item.get("ip") or "",
        ),
        reverse=True,
    )

    observation_summary = (
        legacy_dynamic.get("network_observation_summary")
        if isinstance(legacy_dynamic.get("network_observation_summary"), dict)
        else {}
    )
    source_breakdown = _normalize_source_breakdown(getattr(dynamic_row, "source_breakdown", None))
    if not source_breakdown:
        source_breakdown = _normalize_source_breakdown(observation_summary.get("source_breakdown"))
    if not source_breakdown:
        source_breakdown = _build_source_breakdown(observations)

    observation_hits = int(getattr(dynamic_row, "total_observations", 0) or 0)
    if observation_hits <= 0:
        observation_hits = int(observation_summary.get("total_observations") or observation_summary.get("total_requests") or 0)
    if observation_hits <= 0:
        observation_hits = sum(int(item.get("hit_count") or 0) for item in observations)
    if observation_hits <= 0:
        observation_hits = int(getattr(dynamic_row, "total_requests", 0) or 0)

    domains_count = int(getattr(dynamic_row, "unique_domains", 0) or observation_summary.get("unique_domains") or 0)
    domains_count = max(domains_count, len(top_domains))

    top_ips = _build_ip_stats(observations)
    ips_count = int(getattr(dynamic_row, "unique_ips", 0) or observation_summary.get("unique_ips") or 0)
    if ips_count <= 0:
        ips_count = len(top_ips)

    if not capture_mode and (top_domains or top_ips or source_breakdown or observations):
        capture_mode = "redroid_zeek"

    screenshots: list[dict[str, Any]]
    if screenshot_rows:
        screenshots = [
            {
                "id": row.id,
                "image_url": _report_screenshot_image_url(task_id, row.id, bool(row.storage_path)),
                "file_size": int(row.file_size or 0),
                "stage": row.stage,
                "description": row.description,
                "captured_at": _isoformat(row.captured_at),
            }
            for row in screenshot_rows
        ]
    else:
        screenshots = []
        for index, row in enumerate(_legacy_screenshots(legacy_dynamic)):
            image_url = None
            if row.get("storage_path") or row.get("image_base64"):
                image_url = f"/api/v1/frontend/reports/{task_id}/screenshots/legacy-{index}"
            screenshots.append(
                {
                    "id": f"legacy-{index}",
                    "image_url": image_url,
                    "file_size": int(row.get("file_size", 0) or 0),
                    "stage": row.get("stage"),
                    "description": row.get("description"),
                    "captured_at": row.get("captured_at"),
                }
            )

    risk_level = _risk_level(
        static_row,
        dynamic_row,
        legacy_static,
        domain_count=len(top_domains),
        observation_hits=observation_hits,
    )
    risk_label = _risk_label(risk_level)
    app_name = _app_name(task, static_row, dynamic_row, legacy_static)
    package_name = _package_name(static_row, dynamic_row, legacy_static)
    screenshot_count = len(screenshots)

    return {
        "task": {
            "id": task.id,
            "app_name": app_name,
            "package_name": package_name,
            "apk_file_name": task.apk_file_name,
            "apk_file_size": int(task.apk_file_size),
            "apk_md5": task.apk_md5,
            "status": _status_value(task.status),
            "risk_level": risk_level,
            "created_at": _isoformat(task.created_at),
            "completed_at": _isoformat(task.completed_at),
        },
        "static_info": _static_info(task, static_row, dynamic_row, legacy_static),
        "permission_summary": _permission_summary(dynamic_row, legacy_dynamic),
        "summary": {
            "risk_level": risk_level,
            "risk_label": risk_label,
            "conclusion": (
                f"该应用当前被判定为{risk_label}。被动观测显示 {domains_count} 个主域名、"
                f"{ips_count} 个关键 IP 端点、{observation_hits} 次观测命中。"
            ),
            "highlights": [
                f"识别到 {domains_count} 个高价值主域名",
                f"归并出 {ips_count} 个关键 IP 端点",
                f"保留 {screenshot_count} 张动态截图",
            ],
        },
        "evidence_summary": {
            "domains_count": domains_count,
            "ips_count": ips_count,
            "observation_hits": observation_hits,
            "source_breakdown": source_breakdown,
            "capture_mode": capture_mode,
            "screenshots_count": screenshot_count,
        },
        "top_domains": top_domains[:TOP_DOMAIN_LIMIT],
        "top_ips": top_ips[:TOP_IP_LIMIT],
        "timeline": observations[:TIMELINE_LIMIT],
        "screenshots": screenshots,
        "download_url": f"/api/v1/reports/{task_id}/download",
    }


def build_frontend_report_download_context(
    db: Session,
    task_id: str,
    *,
    require_completed: bool = True,
) -> dict[str, Any] | None:
    """Build a flattened HTML-download context from the frontend report DTO."""
    task = _task_or_404(db, task_id)
    if not task:
        return None
    if require_completed:
        _ensure_completed(task)

    report = build_frontend_report(db, task_id, require_completed=require_completed)
    if report is None:
        return None

    return {
        **report,
        "app_name": report["task"]["app_name"],
        "package_name": report["task"]["package_name"] or "未知应用",
        "risk_level": report["summary"]["risk_level"],
        "risk_label": report["summary"]["risk_label"],
        "analysis_date": report["task"]["completed_at"] or report["task"]["created_at"],
        "apk_file_name": report["task"]["apk_file_name"],
        "apk_file_size": report["task"]["apk_file_size"],
        "apk_md5": report["task"]["apk_md5"],
        "static_analysis_result": _legacy_static_result(task),
        "dynamic_analysis_result": _legacy_dynamic_result(task),
    }


def resolve_frontend_report_screenshot_source(
    db: Session,
    task_id: str,
    screenshot_ref: str,
    *,
    require_completed: bool = True,
) -> FrontendReportScreenshotSource | None:
    """Resolve a screenshot reference to storage or inline bytes without embedding base64 in DTOs."""
    task = _task_or_404(db, task_id)
    if not task:
        return None
    if require_completed:
        _ensure_completed(task)

    row = (
        db.query(ScreenshotTable)
        .filter(ScreenshotTable.task_id == task_id, ScreenshotTable.id == screenshot_ref)
        .first()
    )
    if row and row.storage_path:
        return FrontendReportScreenshotSource(storage_path=row.storage_path)

    if not screenshot_ref.startswith("legacy-"):
        return None

    try:
        legacy_index = int(screenshot_ref.split("-", 1)[1])
    except (IndexError, ValueError):
        return None

    screenshots = _legacy_screenshots(_legacy_dynamic_result(task))
    if legacy_index < 0 or legacy_index >= len(screenshots):
        return None

    screenshot = screenshots[legacy_index]
    image_base64 = screenshot.get("image_base64")
    content_type = "image/png"
    if isinstance(image_base64, str) and image_base64.startswith("data:") and "," in image_base64:
        header, encoded = image_base64.split(",", 1)
        image_base64 = encoded
        content_type = header[5:].split(";")[0] or "image/png"

    storage_path = screenshot.get("storage_path")
    if storage_path:
        return FrontendReportScreenshotSource(
            storage_path=storage_path,
            content_type=content_type,
        )
    if isinstance(image_base64, str) and image_base64:
        return FrontendReportScreenshotSource(
            image_base64=image_base64,
            content_type=content_type,
        )
    return None


def resolve_frontend_report_icon_source(
    db: Session,
    task_id: str,
    *,
    require_completed: bool = True,
) -> FrontendReportIconSource | None:
    """Resolve report icon source for frontend report icon requests."""
    task = _task_or_404(db, task_id)
    if not task:
        return None
    if require_completed:
        _ensure_completed(task)

    legacy_static = _legacy_static_result(task)
    basic_info = legacy_static.get("basic_info") if isinstance(legacy_static.get("basic_info"), dict) else legacy_static
    storage_path = basic_info.get("icon_storage_path")
    if isinstance(storage_path, str) and storage_path:
        return FrontendReportIconSource(
            storage_path=storage_path,
            content_type=str(basic_info.get("icon_content_type") or "image/png"),
        )
    return None
