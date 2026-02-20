"""Report generator Celery task."""
import logging
from typing import Optional
import io

from celery import shared_task
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.report_generator import ReportGenerator, generate_analysis_report

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="workers.report_generator.generate_report")
def generate_report(self, task_id: str) -> dict:
    """
    Generate PDF analysis report for a task.

    Args:
        task_id: Task ID to generate report for

    Returns:
        Report generation result dict
    """
    db: Session = SessionLocal()

    try:
        # Get task from database
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        task.status = TaskStatus.REPORT_GENERATING
        db.commit()

        logger.info(f"Starting report generation for task {task_id}")

        # Get task data
        task_data = {
            "id": task.id,
            "package_name": task.apk_file_name,
            "apk_file_size": task.apk_file_size,
            "apk_md5": task.apk_md5,
            "apk_sha256": task.apk_sha256,
        }

        # Get analysis results
        static_result = task.static_analysis_result
        dynamic_result = task.dynamic_analysis_result

        # Extract network requests from dynamic analysis
        network_requests = []
        if dynamic_result and "suspicious_requests" in dynamic_result:
            network_requests = dynamic_result["suspicious_requests"]

        # Extract screenshots from dynamic analysis
        screenshots = []
        if dynamic_result and "exploration_result" in dynamic_result:
            exploration_result = dynamic_result["exploration_result"]
            if isinstance(exploration_result, dict) and "screenshots" in exploration_result:
                screenshots = exploration_result["screenshots"]

        # Generate report data
        report_data = generate_analysis_report(
            task_data=task_data,
            static_result=static_result,
            dynamic_result=dynamic_result,
            network_requests=network_requests,
            screenshots=screenshots,
        )

        # Generate PDF
        generator = ReportGenerator()

        # Generate PDF to bytes first
        pdf_bytes = generator.generate_report(
            analysis_data=report_data,
            template_name="report.html",
            output_path=None,  # Return bytes
        )

        # Upload to MinIO
        report_path = f"reports/{task_id}/report.pdf"
        storage_client.upload_file(
            data=pdf_bytes,
            object_name=report_path,
            content_type="application/pdf",
        )

        # Update task
        task.report_storage_path = report_path
        task.status = TaskStatus.COMPLETED
        task.completed_at = func.now()
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
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise

    finally:
        db.close()


# Import func for database timestamp
from sqlalchemy import func
