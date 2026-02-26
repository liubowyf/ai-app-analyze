import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from api.routers.reports import view_report, download_report


def test_view_report_task_not_found():
    """测试查看不存在的任务报告"""
    # Mock数据库会话
    mock_db = Mock()
    mock_db.query().filter().first.return_value = None

    # 测试应该抛出404异常
    with pytest.raises(HTTPException) as exc_info:
        view_report("nonexistent_task", mock_db)

    assert exc_info.value.status_code == 404
    assert "Task not found" in str(exc_info.value.detail)


def test_download_report_task_not_found():
    """测试下载不存在的任务报告"""
    # Mock数据库会话
    mock_db = Mock()
    mock_db.query().filter().first.return_value = None

    # 测试应该抛出404异常
    with pytest.raises(HTTPException) as exc_info:
        download_report("nonexistent_task", mock_db)

    assert exc_info.value.status_code == 404
    assert "Task not found" in str(exc_info.value.detail)


def test_view_report_task_not_completed():
    """测试查看未完成任务的报告"""
    # Mock任务对象
    mock_task = Mock()
    mock_task.status = "pending"

    # Mock数据库会话
    mock_db = Mock()
    mock_db.query().filter().first.return_value = mock_task

    # 测试应该抛出400异常
    with pytest.raises(HTTPException) as exc_info:
        view_report("pending_task", mock_db)

    assert exc_info.value.status_code == 400
    assert "Task not completed yet" in str(exc_info.value.detail)


@patch('api.routers.reports.HTMLReportGenerator')
def test_view_report_success(mock_generator_class):
    """测试成功查看报告"""
    # Mock任务对象
    mock_task = Mock()
    mock_task.id = "test_task_123"
    mock_task.status = "completed"
    mock_task.package_name = "com.test.app"
    mock_task.created_at = None

    # Mock数据库会话
    mock_db = Mock()
    mock_db.query().filter().first.return_value = mock_task

    # Mock HTML生成器
    mock_generator = Mock()
    mock_generator.generate_web_report.return_value = "<html><body>Test Report</body></html>"
    mock_generator_class.return_value = mock_generator

    # 调用函数
    response = view_report("test_task_123", mock_db)

    # 验证响应
    assert response.media_type == "text/html"
    assert "<html><body>Test Report</body></html>" in response.body.decode()


@patch('api.routers.reports.HTMLReportGenerator')
def test_download_report_success(mock_generator_class):
    """测试成功下载报告"""
    # Mock任务对象
    mock_task = Mock()
    mock_task.id = "test_task_123"
    mock_task.status = "completed"
    mock_task.package_name = "com.test.app"
    mock_task.created_at = None

    # Mock数据库会话
    mock_db = Mock()
    mock_db.query().filter().first.return_value = mock_task

    # Mock HTML生成器
    mock_generator = Mock()
    mock_generator.generate_static_report.return_value = "<html><body>Static Report</body></html>"
    mock_generator_class.return_value = mock_generator

    # 调用函数
    response = download_report("test_task_123", mock_db)

    # 验证响应
    assert response.media_type == "text/html"
    assert "attachment" in response.headers["content-disposition"]
    assert "report_test_task_123.html" in response.headers["content-disposition"]
    assert "<html><body>Static Report</body></html>" in response.body.decode()