import pytest
from fastapi.testclient import TestClient
from api.main import app


client = TestClient(app)


def test_view_report_endpoint():
    """测试在线查看报告端点"""
    # 这里需要一个有效的task_id，暂时使用测试ID
    task_id = "test_task_123"
    response = client.get(f"/api/v1/reports/{task_id}/view")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_download_report_endpoint():
    """测试下载报告端点"""
    task_id = "test_task_123"
    response = client.get(f"/api/v1/reports/{task_id}/download")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "text/html" in response.headers["content-type"]


def test_view_report_not_found():
    """测试查看不存在的报告"""
    task_id = "nonexistent_task"
    response = client.get(f"/api/v1/reports/{task_id}/view")
    assert response.status_code == 404


def test_download_report_not_found():
    """测试下载不存在的报告"""
    task_id = "nonexistent_task"
    response = client.get(f"/api/v1/reports/{task_id}/download")
    assert response.status_code == 404