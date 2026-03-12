"""Frontend-oriented backend-for-frontend routes."""

from __future__ import annotations

import base64
import binascii
import logging
import mimetypes

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.schemas.frontend import (
    FrontendRiskLevel,
    FrontendTaskListResponse,
)
from core.database import get_db
from core.storage import storage_client
from models.task import Task, TaskPriority, TaskStatus
from modules.frontend_presenters.report import (
    build_frontend_report,
    resolve_frontend_report_screenshot_source,
)
from modules.frontend_presenters.task_detail import (
    build_frontend_task_detail,
    resolve_frontend_task_detail_screenshot_source,
)
from modules.frontend_presenters.tasks import build_frontend_task_list
from modules.task_orchestration.queue_backend import enqueue_task
from modules.upload_batch.service import BatchUploadFile, BatchUploadService

router = APIRouter()
logger = logging.getLogger(__name__)


def _task_status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


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

    return Response(content=data, media_type=content_type)


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
            status=TaskStatus.PENDING,
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


@router.post("/tasks/{task_id}/retry")
def retry_frontend_task(task_id: str, db: Session = Depends(get_db)):
    """Retry a failed task and return the refreshed frontend detail payload."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    task.status = TaskStatus.QUEUED
    task.retry_count += 1
    task.error_message = None
    task.error_stack = None
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
