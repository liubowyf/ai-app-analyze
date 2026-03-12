import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.database import get_db
from models.task import Task
from modules.frontend_presenters.report import build_frontend_report_download_context
from modules.report_generator.html_generator import HTMLReportGenerator

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/reports/{task_id}/download")
def download_report(task_id: str, db: Session = Depends(get_db)):
    """下载静态HTML报告"""
    # 获取任务信息
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    try:
        generator = HTMLReportGenerator()
        report_data = build_frontend_report_download_context(db, task_id)
        if report_data is None:
            raise HTTPException(status_code=404, detail="Task not found")

        html = generator.generate_static_report(report_data)
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=report_{task_id}.html"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate static report for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")
