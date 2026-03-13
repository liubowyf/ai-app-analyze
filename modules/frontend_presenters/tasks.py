"""Presenter helpers for frontend task list responses."""

from __future__ import annotations

from math import ceil
from typing import Any, Optional

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from api.schemas.frontend import (
    FrontendPagination,
    FrontendRiskLevel,
    FrontendTaskListItem,
    FrontendTaskListResponse,
)
from models.analysis_tables import DynamicAnalysisTable, StaticAnalysisTable
from models.task import Task, TaskStatus


def _risk_level_expression():
    """Build a stable risk-level mapping from normalized analysis fields."""
    static_risk = func.lower(func.coalesce(StaticAnalysisTable.risk_level, ""))
    master_domains = func.coalesce(DynamicAnalysisTable.master_domains, 0)
    total_requests = func.coalesce(DynamicAnalysisTable.total_requests, 0)

    return case(
        (static_risk.in_(("critical", "high")), FrontendRiskLevel.HIGH.value),
        (static_risk == "medium", FrontendRiskLevel.MEDIUM.value),
        (static_risk == "low", FrontendRiskLevel.LOW.value),
        (master_domains >= 2, FrontendRiskLevel.HIGH.value),
        (
            or_(master_domains >= 1, total_requests > 20),
            FrontendRiskLevel.MEDIUM.value,
        ),
        (total_requests > 0, FrontendRiskLevel.LOW.value),
        else_=FrontendRiskLevel.UNKNOWN.value,
    )


def _status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _isoformat(value: object) -> Optional[str]:
    return value.isoformat() if value else None


def _report_ready(status: object) -> bool:
    return _status_value(status) == TaskStatus.COMPLETED.value


def _legacy_basic_info(row: object) -> dict[str, Any]:
    static_result = getattr(row, "task_static_analysis_result", None)
    if not isinstance(static_result, dict):
        return {}

    basic_info = static_result.get("basic_info")
    if isinstance(basic_info, dict):
        return basic_info

    return static_result


def _package_name(row: object) -> Optional[str]:
    return (
        getattr(row, "static_package_name", None)
        or getattr(row, "detected_package", None)
        or _legacy_basic_info(row).get("package_name")
    )


def _app_name(row: object) -> str:
    app_name = getattr(row, "app_name", None)
    if app_name:
        return app_name

    legacy_app_name = _legacy_basic_info(row).get("app_name")
    if isinstance(legacy_app_name, str) and legacy_app_name:
        return legacy_app_name

    package_name = _package_name(row)
    if package_name:
        return package_name.rsplit(".", 1)[-1]

    apk_file_name = getattr(row, "apk_file_name", "unknown.apk")
    return apk_file_name.rsplit(".", 1)[0]


def _to_frontend_task_item(row: object) -> FrontendTaskListItem:
    """Convert a lightweight query row into a frontend DTO."""
    status = _status_value(getattr(row, "status"))
    report_ready = _report_ready(status)
    task_id = getattr(row, "id")

    return FrontendTaskListItem(
        id=task_id,
        app_name=_app_name(row),
        package_name=_package_name(row),
        apk_file_name=getattr(row, "apk_file_name"),
        apk_file_size=int(getattr(row, "apk_file_size")),
        apk_md5=getattr(row, "apk_md5"),
        status=status,
        risk_level=FrontendRiskLevel(getattr(row, "risk_level") or FrontendRiskLevel.UNKNOWN.value),
        created_at=_isoformat(getattr(row, "created_at")),
        completed_at=_isoformat(getattr(row, "completed_at")),
        report_ready=report_ready,
        report_url=f"/reports/{task_id}" if report_ready else None,
    )


def build_frontend_task_list(
    db: Session,
    *,
    page: int,
    page_size: int,
    search: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    risk_level: Optional[FrontendRiskLevel] = None,
    report_ready: Optional[bool] = None,
) -> FrontendTaskListResponse:
    """Fetch and present a lightweight, page-oriented task list."""
    risk_level_expr = _risk_level_expression().label("risk_level")
    query = (
        db.query(
            Task.id.label("id"),
            Task.apk_file_name.label("apk_file_name"),
            Task.apk_file_size.label("apk_file_size"),
            Task.apk_md5.label("apk_md5"),
            Task.status.label("status"),
            Task.created_at.label("created_at"),
            Task.completed_at.label("completed_at"),
            Task.static_analysis_result.label("task_static_analysis_result"),
            StaticAnalysisTable.app_name.label("app_name"),
            StaticAnalysisTable.package_name.label("static_package_name"),
            DynamicAnalysisTable.detected_package.label("detected_package"),
            risk_level_expr,
        )
        .select_from(Task)
        .outerjoin(StaticAnalysisTable, StaticAnalysisTable.task_id == Task.id)
        .outerjoin(DynamicAnalysisTable, DynamicAnalysisTable.task_id == Task.id)
    )

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Task.id.ilike(search_term),
                Task.apk_file_name.ilike(search_term),
                StaticAnalysisTable.app_name.ilike(search_term),
                StaticAnalysisTable.package_name.ilike(search_term),
                DynamicAnalysisTable.detected_package.ilike(search_term),
            )
        )

    if status is not None:
        query = query.filter(Task.status == status.value)

    if risk_level is not None:
        query = query.filter(risk_level_expr == risk_level.value)

    if report_ready is True:
        query = query.filter(Task.status == TaskStatus.COMPLETED.value)
    elif report_ready is False:
        query = query.filter(Task.status != TaskStatus.COMPLETED.value)

    total = query.count()
    offset = (page - 1) * page_size
    rows = (
        query.order_by(Task.created_at.desc(), Task.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [_to_frontend_task_item(row) for row in rows]
    total_pages = ceil(total / page_size) if total else 0

    return FrontendTaskListResponse(
        items=items,
        pagination=FrontendPagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )
