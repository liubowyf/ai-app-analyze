from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from core.database import get_db
from models.task import Task
from modules.report_generator.html_generator import HTMLReportGenerator
from core.storage import storage_client
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/reports/{task_id}/view")
def view_report(task_id: str, db: Session = Depends(get_db)):
    """在线查看HTML报告"""
    # 获取任务信息
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    # 检查是否已有HTML报告
    if hasattr(task, 'web_report_path') and task.web_report_path:
        try:
            # 从存储中获取HTML内容
            html_content = storage_client.get_file_content(task.web_report_path)
            return Response(content=html_content, media_type="text/html")
        except Exception as e:
            logger.warning(f"Failed to get existing web report: {e}")

    # 如果没有HTML报告，动态生成
    try:
        generator = HTMLReportGenerator()

        # 构建报告数据
        report_data = {
            "task_id": task.id,
            "package_name": task.package_name,
            "app_name": getattr(task, 'app_name', None),
            "risk_level": getattr(task, 'risk_level', 'unknown').lower(),
            "analysis_date": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
            # 可以添加更多字段
        }

        html = generator.generate_web_report(report_data)
        return Response(content=html, media_type="text/html")

    except Exception as e:
        logger.error(f"Failed to generate web report for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/reports/{task_id}/download")
def download_report(task_id: str, db: Session = Depends(get_db)):
    """下载静态HTML报告"""
    # 获取任务信息
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    # 检查是否已有静态HTML报告
    if hasattr(task, 'static_report_path') and task.static_report_path:
        try:
            # 从存储中获取HTML内容
            html_content = storage_client.get_file_content(task.static_report_path)
            return Response(
                content=html_content,
                media_type="text/html",
                headers={"Content-Disposition": f"attachment; filename=report_{task_id}.html"}
            )
        except Exception as e:
            logger.warning(f"Failed to get existing static report: {e}")

    # 如果没有静态HTML报告，动态生成
    try:
        generator = HTMLReportGenerator()

        # 构建报告数据
        report_data = {
            "task_id": task.id,
            "package_name": task.package_name,
            "app_name": getattr(task, 'app_name', None),
            "risk_level": getattr(task, 'risk_level', 'unknown').lower(),
            "analysis_date": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
        }

        html = generator.generate_static_report(report_data)
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=report_{task_id}.html"}
        )

    except Exception as e:
        logger.error(f"Failed to generate static report for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")