"""Frontend-oriented backend-for-frontend routes."""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import mimetypes
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from api.schemas.frontend import (
    FrontendRiskLevel,
    FrontendRuntimeStatusResponse,
    FrontendTaskListResponse,
)
from core.config import settings
from core.database import get_db
from core.storage import storage_client
from models.analysis_tables import (
    AnalysisRunTable,
    DynamicAnalysisTable,
    MasterDomainTable,
    NetworkRequestTable,
    RedroidLeaseTable,
    ScreenshotTable,
    StaticAnalysisTable,
)
from models.task import Task, TaskPriority, TaskStatus
from modules.frontend_presenters.report import (
    build_frontend_report,
    resolve_frontend_report_icon_source,
    resolve_frontend_report_screenshot_source,
)
from modules.frontend_presenters.task_detail import (
    build_frontend_task_detail,
    resolve_frontend_task_icon_source,
    resolve_frontend_task_detail_screenshot_source,
)
from modules.frontend_presenters.tasks import build_frontend_task_list
from modules.redroid_remote.host_agent_client import HostAgentError, RedroidHostAgentClient
from modules.task_orchestration.queue_backend import enqueue_task, get_backend_runtime_diagnostics
from modules.task_orchestration.state_machine import manual_retry_status
from modules.upload_batch.service import BatchUploadFile, BatchUploadService

router = APIRouter()
logger = logging.getLogger(__name__)


def _task_status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _has_static_analysis_result(db: Session, task: Task) -> bool:
    """Return whether the task already has reusable static-analysis output."""
    static_result = getattr(task, "static_analysis_result", None)
    if isinstance(static_result, dict) and static_result:
        return True
    return (
        db.query(StaticAnalysisTable.id)
        .filter(StaticAnalysisTable.task_id == task.id)
        .first()
        is not None
    )


def _build_frontend_runtime_status(db: Session) -> dict[str, object]:
    diagnostics = get_backend_runtime_diagnostics()
    rows = db.query(Task.status, func.count(Task.id)).group_by(Task.status).all()
    by_status: dict[str, int] = {}
    for status, count in rows:
        by_status[_task_status_value(status)] = int(count)

    active_leases = {
        row.slot_key: row
        for row in db.query(RedroidLeaseTable)
        .filter(RedroidLeaseTable.holder_task_id.isnot(None))
        .all()
    }

    slots_payload: list[dict[str, object]] = []
    healthy_slots = 0
    slots_by_name: dict[str, dict[str, object]] = {}
    agent_error: str | None = None
    if settings.REDROID_HOST_AGENT_BASE_URL:
        try:
            client = RedroidHostAgentClient(
                settings.REDROID_HOST_AGENT_BASE_URL,
                token=settings.REDROID_HOST_AGENT_TOKEN or None,
                timeout=settings.REDROID_HOST_AGENT_TIMEOUT_SECONDS,
            )
            slots = client.list_slots()
            for item in slots:
                slot_name = str(item.get("slot_name") or "").strip()
                if slot_name:
                    slots_by_name[slot_name] = item
        except HostAgentError as exc:
            agent_error = str(exc)
        except Exception as exc:
            agent_error = str(exc)
    else:
        agent_error = "host_agent_unconfigured"

    for slot in settings.redroid_slots:
        slot_name = str(slot.get("name") or slot.get("adb_serial") or "unknown")
        container_name = str(slot.get("container_name") or slot_name)
        lease = active_leases.get(slot_name)
        slot_runtime = slots_by_name.get(slot_name, {})
        healthy = bool(slot_runtime.get("healthy", False))
        detail = str(slot_runtime.get("detail") or "").strip() or None
        if not slots_by_name:
            healthy = False
            detail = agent_error
        elif not slot_runtime:
            healthy = False
            detail = "slot_not_reported_by_host_agent"

        if healthy:
            healthy_slots += 1

        slots_payload.append(
            {
                "slot_name": slot_name,
                "container_name": container_name,
                "healthy": healthy,
                "busy": lease is not None,
                "holder_task_id": getattr(lease, "holder_task_id", None),
                "detail": detail,
            }
        )

    return {
        "api_healthy": True,
        "worker_ready": bool(diagnostics.get("dramatiq_ready", False)),
        "queue_backend": str(diagnostics.get("backend", "dramatiq")),
        "tasks": {
            "queued_count": by_status.get("queued", 0),
            "static_running_count": by_status.get("static_analyzing", 0),
            "dynamic_running_count": by_status.get("dynamic_analyzing", 0),
            "report_running_count": by_status.get("report_generating", 0),
            "running_count": sum(
                by_status.get(key, 0)
                for key in ("static_analyzing", "dynamic_analyzing", "report_generating")
            ),
        },
        "redroid": {
            "configured_slots": len(settings.redroid_slots),
            "healthy_slots": healthy_slots,
            "busy_slots": sum(1 for item in slots_payload if item["busy"]),
            "slots": slots_payload,
        },
        "checked_at": datetime.utcnow().isoformat(),
    }


def _build_created_task_item(task: Task) -> dict[str, object]:
    return {
        "id": task.id,
        "app_name": task.apk_file_name.rsplit(".", 1)[0],
        "package_name": None,
        "apk_file_name": task.apk_file_name,
        "apk_file_size": task.apk_file_size,
        "apk_md5": task.apk_md5,
        "status": _task_status_value(task.status),
        "risk_level": FrontendRiskLevel.UNKNOWN.value,
        "icon_url": None,
        "retryable": False,
        "deletable": True,
        "failure_reason": None,
        "submitter": None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "report_ready": False,
        "report_url": None,
    }


def _format_rejected_file(error: object) -> dict[str, str]:
    archive_entry_name = getattr(error, "archive_entry_name", None)
    source_file_name = getattr(error, "source_file_name", "unknown")
    file_name = archive_entry_name or source_file_name
    if archive_entry_name:
        file_name = f"{source_file_name}:{archive_entry_name}"

    return {
        "file_name": file_name,
        "reason": getattr(error, "message", "Upload rejected."),
    }


def _format_upload_message(created_count: int, rejected_count: int) -> str:
    if created_count and rejected_count:
        return f"成功创建 {created_count} 个任务，{rejected_count} 个文件被拒绝。"
    if created_count:
        return f"成功创建 {created_count} 个任务。"
    return f"未创建任务，{rejected_count} 个文件被拒绝。"


def _resolve_existing_apk_storage_path(db: Session, apk_md5: str) -> str | None:
    """Reuse an existing stored APK object when the same content was uploaded before."""
    row = (
        db.query(Task.apk_storage_path)
        .filter(Task.apk_md5 == apk_md5)
        .filter(Task.apk_storage_path.isnot(None))
        .order_by(desc(Task.created_at))
        .first()
    )
    if not row:
        return None
    value = row[0] if isinstance(row, tuple) else getattr(row, "apk_storage_path", None)
    return value or None


def _build_frontend_image_response(source: object) -> Response:
    content_type = (
        getattr(source, "content_type", None)
        or mimetypes.guess_type(getattr(source, "storage_path", None) or "")[0]
        or "image/png"
    )
    data: bytes | None = None

    storage_path = getattr(source, "storage_path", None)
    if storage_path:
        data = storage_client.download_file(storage_path)
    else:
        image_base64 = getattr(source, "image_base64", None)
        if image_base64:
            try:
                data = base64.b64decode(image_base64)
            except (ValueError, binascii.Error) as exc:
                raise HTTPException(status_code=404, detail="Screenshot not found") from exc

    if not data:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    etag = hashlib.md5(data).hexdigest()
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Length": str(len(data)),
            "ETag": etag,
        },
    )


@router.get("/tasks", response_model=FrontendTaskListResponse)
def list_frontend_tasks(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: str | None = Query(None, description="Search by task id, app name, package, or file name"),
    status: TaskStatus | None = Query(None, description="Filter by task status"),
    risk_level: FrontendRiskLevel | None = Query(None, description="Filter by frontend risk level"),
    report_ready: bool | None = Query(None, description="Filter by report availability"),
    db: Session = Depends(get_db),
):
    """Return a paginated task list tailored for the frontend list page."""
    return build_frontend_task_list(
        db,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        risk_level=risk_level,
        report_ready=report_ready,
    )


@router.get("/runtime-status", response_model=FrontendRuntimeStatusResponse)
def get_frontend_runtime_status(db: Session = Depends(get_db)):
    """Return a lightweight runtime health summary for the list page."""
    return _build_frontend_runtime_status(db)


@router.post("/tasks/upload")
async def upload_frontend_tasks(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload multiple APK/ZIP files and create batch tasks for the frontend."""
    uploads = [
        BatchUploadFile(
            filename=file.filename or "",
            content=await file.read(),
            content_type=file.content_type,
        )
        for file in files
    ]
    batch_service = BatchUploadService(
        storage=storage_client,
        existing_apk_resolver=lambda apk_md5: _resolve_existing_apk_storage_path(db, apk_md5),
    )
    batch_result = batch_service.prepare_batch(uploads)

    created_tasks: list[Task] = []
    for task_input in batch_result.task_inputs:
        task = Task(
            id=task_input.task_id,
            apk_file_name=task_input.apk_file_name,
            apk_file_size=task_input.apk_file_size,
            apk_md5=task_input.apk_md5,
            apk_storage_path=task_input.apk_storage_path,
            status=TaskStatus.QUEUED,
            priority=TaskPriority.BATCH,
        )
        db.add(task)
        created_tasks.append(task)

    if created_tasks:
        db.commit()
        for task in created_tasks:
            db.refresh(task)
            enqueue_ok = enqueue_task(str(task.id), priority=task.priority)
            if not enqueue_ok:
                logger.warning("Failed to enqueue analysis workflow for task %s", task.id)

    extracted_apk_count = sum(
        1 for task_input in batch_result.task_inputs if task_input.source_kind == "zip_apk"
    )

    return {
        "accepted_files": [task_input.apk_file_name for task_input in batch_result.task_inputs],
        "rejected_files": [_format_rejected_file(error) for error in batch_result.errors],
        "created_tasks": [_build_created_task_item(task) for task in created_tasks],
        "extracted_apk_count": extracted_apk_count,
        "message": _format_upload_message(
            created_count=len(created_tasks),
            rejected_count=len(batch_result.errors),
        ),
    }


@router.get("/tasks/{task_id}")
def get_frontend_task_detail(task_id: str, db: Session = Depends(get_db)):
    """Return a frontend-friendly aggregated task detail payload."""
    detail = build_frontend_task_detail(db, task_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return detail


@router.get("/tasks/{task_id}/screenshots/{screenshot_ref}")
def get_frontend_task_detail_screenshot(
    task_id: str,
    screenshot_ref: str,
    db: Session = Depends(get_db),
):
    """Serve task detail screenshots through URL-based resource references."""
    source = resolve_frontend_task_detail_screenshot_source(db, task_id, screenshot_ref)
    if source is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return _build_frontend_image_response(source)


@router.get("/tasks/{task_id}/icon")
def get_frontend_task_icon(
    task_id: str,
    db: Session = Depends(get_db),
):
    """Serve task icon through URL-based resource references."""
    source = resolve_frontend_task_icon_source(db, task_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Icon not found")
    return _build_frontend_image_response(source)


@router.get("/reports/{task_id}")
def get_frontend_report(task_id: str, db: Session = Depends(get_db)):
    """Return a frontend-friendly aggregated report payload."""
    try:
        report = build_frontend_report(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if report is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return report


@router.get("/reports/{task_id}/screenshots/{screenshot_ref}")
def get_frontend_report_screenshot(
    task_id: str,
    screenshot_ref: str,
    db: Session = Depends(get_db),
):
    """Serve report screenshots through URL-based resource references."""
    try:
        source = resolve_frontend_report_screenshot_source(db, task_id, screenshot_ref)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if source is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return _build_frontend_image_response(source)


@router.get("/reports/{task_id}/icon")
def get_frontend_report_icon(
    task_id: str,
    db: Session = Depends(get_db),
):
    """Serve report icon through URL-based resource references."""
    try:
        source = resolve_frontend_report_icon_source(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if source is None:
        raise HTTPException(status_code=404, detail="Icon not found")
    return _build_frontend_image_response(source)


@router.post("/tasks/{task_id}/retry")
def retry_frontend_task(task_id: str, db: Session = Depends(get_db)):
    """Retry a failed task and return the refreshed frontend detail payload."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = manual_retry_status(
        task.status,
        has_static_result=_has_static_analysis_result(db, task),
        last_success_stage=task.last_success_stage,
    )
    task.retry_count += 1
    task.error_message = None
    task.error_stack = None
    task.failure_reason = None
    task.dynamic_analysis_result = None
    task.report_storage_path = None
    task.web_report_path = None
    task.completed_at = None
    db.commit()
    db.refresh(task)

    enqueue_ok = enqueue_task(str(task.id), priority=task.priority)
    if not enqueue_ok:
        logger.warning("Task %s retry enqueue failed", task.id)

    detail = build_frontend_task_detail(db, task_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return detail


@router.delete("/tasks/{task_id}")
def delete_frontend_task(task_id: str, db: Session = Depends(get_db)):
    """Delete task records from the database without deleting MinIO objects."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.query(AnalysisRunTable).filter(AnalysisRunTable.task_id == task_id).delete(synchronize_session=False)
    db.query(NetworkRequestTable).filter(NetworkRequestTable.task_id == task_id).delete(synchronize_session=False)
    db.query(MasterDomainTable).filter(MasterDomainTable.task_id == task_id).delete(synchronize_session=False)
    db.query(ScreenshotTable).filter(ScreenshotTable.task_id == task_id).delete(synchronize_session=False)
    db.query(DynamicAnalysisTable).filter(DynamicAnalysisTable.task_id == task_id).delete(synchronize_session=False)
    db.query(StaticAnalysisTable).filter(StaticAnalysisTable.task_id == task_id).delete(synchronize_session=False)
    db.delete(task)
    db.commit()
    return {"id": task_id, "deleted": True}
