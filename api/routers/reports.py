import logging
import base64
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.database import get_db
from core.storage import storage_client
from models.task import Task
from modules.report_generator.html_generator import HTMLReportGenerator

logger = logging.getLogger(__name__)
router = APIRouter()


def _hydrate_screenshots_from_storage(screenshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fill image_base64 when screenshot only stores storage_path."""
    hydrated: List[Dict[str, Any]] = []
    for shot in screenshots:
        if not isinstance(shot, dict):
            continue
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


def _extract_dynamic_report_fields(dynamic_result: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], int, List[Dict[str, Any]]]:
    """
    Extract package, domains, requests and screenshots from dynamic result payload.
    """
    package_name = None
    master_domains: List[Dict[str, Any]] = []
    network_requests: List[Dict[str, Any]] = []
    network_requests_count = 0
    screenshots: List[Dict[str, Any]] = []

    if not isinstance(dynamic_result, dict):
        return package_name, master_domains, network_requests, network_requests_count, screenshots

    network_analysis = dynamic_result.get("network_analysis") or {}
    packages = network_analysis.get("packages") if isinstance(network_analysis, dict) else None
    if isinstance(packages, dict) and packages:
        package_name = next(iter(packages.keys()))

    masters = dynamic_result.get("master_domains")
    if isinstance(masters, dict):
        master_domains = masters.get("master_domains") or []

    suspicious_requests = dynamic_result.get("suspicious_requests")
    if isinstance(suspicious_requests, list):
        network_requests = suspicious_requests
    elif isinstance(dynamic_result.get("network_requests"), list):
        network_requests = dynamic_result["network_requests"]

    total_requests = network_analysis.get("total_requests") if isinstance(network_analysis, dict) else None
    if isinstance(total_requests, int):
        network_requests_count = total_requests
    else:
        network_requests_count = len(network_requests)

    exploration = dynamic_result.get("exploration_result")
    if isinstance(exploration, dict) and isinstance(exploration.get("screenshots"), list):
        screenshots = exploration["screenshots"]
    elif isinstance(dynamic_result.get("screenshots"), list):
        screenshots = dynamic_result["screenshots"]

    screenshots = _hydrate_screenshots_from_storage(screenshots)
    return package_name, master_domains, network_requests, network_requests_count, screenshots


def _build_report_data(task: Task) -> Dict[str, Any]:
    """Build report payload shared by web/static routes."""
    dynamic_result = task.dynamic_analysis_result if isinstance(task.dynamic_analysis_result, dict) else {}
    package_from_dynamic, master_domains, network_requests, network_requests_count, screenshots = _extract_dynamic_report_fields(dynamic_result)

    package_name = package_from_dynamic
    app_name = None
    if task.static_table:
        package_name = task.static_table.package_name or package_name
        app_name = task.static_table.app_name or app_name

    risk_level = "unknown"
    if len(master_domains) >= 2:
        risk_level = "high"
    elif len(master_domains) >= 1 or network_requests_count > 20:
        risk_level = "medium"
    elif network_requests_count > 0:
        risk_level = "low"

    return {
        "task_id": task.id,
        "package_name": package_name or "未知应用",
        "app_name": app_name or (package_name.split(".")[-1] if package_name else "未知应用"),
        "risk_level": risk_level,
        "analysis_date": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
        "master_domains": master_domains,
        "network_requests_count": network_requests_count,
        "network_requests": network_requests,
        "screenshots": screenshots,
        "static_analysis": task.static_analysis_result,
        "static_analysis_result": task.static_analysis_result,
        "dynamic_analysis_result": task.dynamic_analysis_result,
    }


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
    web_report_path = getattr(task, "web_report_path", None)
    if isinstance(web_report_path, str) and web_report_path:
        try:
            # 从存储中获取HTML内容
            html_content = storage_client.download_file(web_report_path)
            if not html_content:
                raise ValueError(f"Empty report content: {web_report_path}")
            return Response(content=html_content, media_type="text/html")
        except Exception as e:
            logger.warning(f"Failed to get existing web report: {e}")

    # 如果没有HTML报告，动态生成
    try:
        generator = HTMLReportGenerator()

        report_data = _build_report_data(task)

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
    static_report_path = getattr(task, "static_report_path", None)
    if isinstance(static_report_path, str) and static_report_path:
        try:
            # 从存储中获取HTML内容
            html_content = storage_client.download_file(static_report_path)
            if not html_content:
                raise ValueError(f"Empty report content: {static_report_path}")
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

        report_data = _build_report_data(task)

        html = generator.generate_static_report(report_data)
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=report_{task_id}.html"}
        )

    except Exception as e:
        logger.error(f"Failed to generate static report for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")
