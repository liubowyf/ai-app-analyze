"""Static analysis Celery task."""
import logging
from typing import Optional

from celery import shared_task
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.apk_analyzer.analyzer import ApkAnalyzer

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="workers.static_analyzer.run_static_analysis")
def run_static_analysis(self, task_id: str) -> dict:
    """
    Run static analysis on an APK file.

    Args:
        task_id: Task ID to process

    Returns:
        Analysis result dict
    """
    db: Session = SessionLocal()
    try:
        # Get task from database
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        task.status = TaskStatus.STATIC_ANALYZING
        db.commit()

        logger.info(f"Starting static analysis for task {task_id}")

        # Download APK from MinIO
        apk_content = storage_client.download_file(task.apk_storage_path)

        # Run analysis
        analyzer = ApkAnalyzer()
        result = analyzer.analyze(
            apk_content=apk_content,
            file_size=task.apk_file_size,
            md5=task.apk_md5,
        )

        # Store results - convert datetime to string for JSON serialization
        result_dict = result.model_dump()
        # Convert any datetime objects to ISO format strings
        def convert_datetime(obj):
            """递归转换datetime对象为字符串"""
            if isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            elif hasattr(obj, 'isoformat'):
                return obj.isoformat()
            else:
                return obj

        result_dict = convert_datetime(result_dict)

        task.static_analysis_result = result_dict
        db.commit()

        logger.info(f"Static analysis completed for task {task_id}")

        return {
            "task_id": task_id,
            "status": "success",
            "package_name": result.basic_info.package_name,
        }

    except Exception as e:
        logger.error(f"Static analysis failed for task {task_id}: {e}")
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    finally:
        db.close()
