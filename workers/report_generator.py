"""Report generator stage service."""
import logging
import base64
from typing import Optional, Any

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.frontend_presenters.report import (
    build_frontend_report_download_context,
    resolve_frontend_report_screenshot_source,
)
from modules.report_generator import ReportGenerator
from modules.report_generator.html_generator import HTMLReportGenerator
from modules.task_orchestration.run_tracker import finish_stage_run, start_stage_run

logger = logging.getLogger(__name__)


def _hydrate_screenshots_from_storage(screenshots: list) -> list:
    """
    Fill image_base64 from storage_path when dynamic result stores compact screenshot data.
    """
    hydrated = []
    for shot in screenshots:
        item = dict(shot)
        if not item.get("image_base64") and item.get("storage_path"):
            try:
                data = storage_client.download_file(item["storage_path"])
                if data:
                    item["image_base64"] = base64.b64encode(data).decode("utf-8")
            except Exception as exc:
                logger.warning("Failed to load screenshot from %s: %s", item.get("storage_path"), exc)
        hydrated.append(item)
    return hydrated


def _build_report_context_for_stage(db: Session, task_id: str) -> dict:
    """Build report context using the frontend/domain-IP DTO contract."""
    report_data = build_frontend_report_download_context(
        db,
        task_id,
        require_completed=False,
    )
    if report_data is None:
        raise ValueError(f"Task {task_id} not found")

    evidence_summary = report_data.get("evidence_summary")
    if isinstance(evidence_summary, dict):
        domains_count = int(evidence_summary.get("domains_count") or 0)
        observation_hits = int(evidence_summary.get("observation_hits") or 0)
        screenshots_count = int(evidence_summary.get("screenshots_count") or 0)
        if domains_count <= 0 and observation_hits <= 0 and screenshots_count <= 0:
            raise ValueError("Dynamic analysis evidence missing")

    screenshots = report_data.get("screenshots")
    if not isinstance(screenshots, list):
        return report_data

    hydrated_screenshots = []
    for shot in screenshots:
        if not isinstance(shot, dict):
            continue
        item = dict(shot)
        screenshot_ref = str(item.get("id") or "")
        if screenshot_ref and not item.get("storage_path") and not item.get("image_base64"):
            source = resolve_frontend_report_screenshot_source(
                db,
                task_id,
                screenshot_ref,
                require_completed=False,
            )
            if source:
                if source.storage_path:
                    item["storage_path"] = source.storage_path
                if source.image_base64:
                    item["image_base64"] = source.image_base64
                if source.content_type:
                    item["content_type"] = source.content_type
        hydrated_screenshots.append(item)

    report_data = dict(report_data)
    report_data["screenshots"] = _hydrate_screenshots_from_storage(hydrated_screenshots)
    return report_data


def generate_report(task_id: Any) -> dict:
    """Report stage entrypoint."""
    from modules.task_orchestration.stage_services import run_report_stage

    return run_report_stage(task_id)


def _run_report_stage_impl(task_id: Any) -> dict:
    """
    Generate PDF analysis report for a task.

    Args:
        task_id: Task ID to generate report for

    Returns:
        Report generation result dict
    """
    db: Session = SessionLocal()
    task: Optional[Task] = None
    task_id = _resolve_task_id(task_id)

    try:
        # Get task from database
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        task.status = TaskStatus.REPORT_GENERATING
        start_stage_run(db, task_id=task_id, stage="report")
        db.commit()

        logger.info(f"Starting report generation for task {task_id}")

        dynamic_result = task.dynamic_analysis_result if isinstance(task.dynamic_analysis_result, dict) else {}
        report_data = _build_report_context_for_stage(db, task_id)

        # Generate PDF
        generator = ReportGenerator()

        # Generate PDF to bytes first
        pdf_bytes = generator.generate_report(
            analysis_data=report_data,
            template_name="report_static.html",
            output_path=None,  # Return bytes
        )

        # Upload to MinIO
        report_path = f"reports/{task_id}/report.pdf"
        storage_client.upload_file(
            data=pdf_bytes,
            object_name=report_path,
            content_type="application/pdf",
        )

        # Generate HTML reports
        html_generator = HTMLReportGenerator()

        # Generate web HTML report
        web_html = html_generator.generate_web_report(report_data)
        web_path = f"reports/{task_id}/report_web.html"
        storage_client.upload_file(
            data=web_html.encode('utf-8'),
            object_name=web_path,
            content_type="text/html"
        )

        # Generate static HTML report
        static_html = html_generator.generate_static_report(report_data)
        static_path = f"reports/{task_id}/report_static.html"
        storage_client.upload_file(
            data=static_html.encode('utf-8'),
            object_name=static_path,
            content_type="text/html"
        )

        # Update task with all report paths
        task.report_storage_path = report_path
        task.web_report_path = web_path
        task.static_report_path = static_path
        task.status = TaskStatus.COMPLETED
        task.last_success_stage = "report"
        task.failure_reason = None
        quality_gate = {}
        if isinstance(dynamic_result, dict):
            gate_raw = dynamic_result.get("quality_gate")
            if isinstance(gate_raw, dict):
                quality_gate = gate_raw
        if quality_gate.get("degraded"):
            task.error_message = f"degraded:{quality_gate.get('reason') or 'unknown'}"
        else:
            task.error_message = None
        task.completed_at = func.now()
        finish_stage_run(
            db,
            task_id=task_id,
            stage="report",
            success=True,
            details={"report_path": report_path},
        )
        db.commit()

        logger.info(f"Report generated successfully for task {task_id}")

        return {
            "task_id": task_id,
            "status": "success",
            "report_path": report_path,
        }

    except Exception as e:
        logger.error(f"Report generation failed for task {task_id}: {e}")
        if task:
            task.status = TaskStatus.DYNAMIC_FAILED
            task.error_message = str(e)
            task.failure_reason = str(e)
            finish_stage_run(
                db,
                task_id=task_id,
                stage="report",
                success=False,
                error_message=str(e),
            )
            db.commit()
        raise

    finally:
        db.close()


# Import func for database timestamp
from sqlalchemy import func


def _resolve_task_id(task_ref: Any) -> str:
    """Resolve task input into task_id string."""
    if isinstance(task_ref, str):
        return task_ref
    if isinstance(task_ref, dict):
        candidate = task_ref.get("task_id")
        if isinstance(candidate, str) and candidate:
            return candidate
    raise ValueError(f"Invalid task reference: {task_ref!r}")
