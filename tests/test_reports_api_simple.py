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


@patch("api.routers.reports.HTMLReportGenerator")
def test_view_report_includes_screenshots_from_dynamic_result(mock_generator_class):
    """动态生成在线报告时应传递截图数据给模板。"""
    mock_task = Mock()
    mock_task.id = "test_task_123"
    mock_task.status = "completed"
    mock_task.created_at = None
    mock_task.web_report_path = None
    mock_task.static_table = None
    mock_task.static_analysis_result = {}
    mock_task.dynamic_analysis_result = {
        "exploration_result": {
            "screenshots": [
                {
                    "stage": "phase2",
                    "description": "点击登录按钮后页面",
                    "image_base64": "aGVsbG8=",
                }
            ]
        },
        "suspicious_requests": [{"url": "https://a.example.com", "method": "GET"}],
        "network_analysis": {"total_requests": 1},
        "master_domains": {"master_domains": []},
    }

    mock_db = Mock()
    mock_db.query().filter().first.return_value = mock_task

    mock_generator = Mock()
    mock_generator.generate_web_report.return_value = "<html><body>Test Report</body></html>"
    mock_generator_class.return_value = mock_generator

    response = view_report("test_task_123", mock_db)

    assert response.media_type == "text/html"
    report_data = mock_generator.generate_web_report.call_args[0][0]
    assert report_data["screenshots"]
    assert report_data["screenshots"][0]["stage"] == "phase2"
    assert report_data["network_requests"][0]["url"] == "https://a.example.com"


@patch("api.routers.reports.HTMLReportGenerator")
def test_download_report_includes_screenshots_from_dynamic_result(mock_generator_class):
    """动态生成下载报告时应传递截图数据给模板。"""
    mock_task = Mock()
    mock_task.id = "test_task_123"
    mock_task.status = "completed"
    mock_task.created_at = None
    mock_task.static_report_path = None
    mock_task.static_table = None
    mock_task.static_analysis_result = {}
    mock_task.dynamic_analysis_result = {
        "exploration_result": {
            "screenshots": [
                {
                    "stage": "phase3",
                    "description": "探索页面",
                    "image_base64": "d29ybGQ=",
                }
            ]
        },
        "suspicious_requests": [],
        "network_analysis": {"total_requests": 0},
        "master_domains": {"master_domains": []},
    }

    mock_db = Mock()
    mock_db.query().filter().first.return_value = mock_task

    mock_generator = Mock()
    mock_generator.generate_static_report.return_value = "<html><body>Static Report</body></html>"
    mock_generator_class.return_value = mock_generator

    response = download_report("test_task_123", mock_db)

    assert response.media_type == "text/html"
    report_data = mock_generator.generate_static_report.call_args[0][0]
    assert report_data["screenshots"]
    assert report_data["screenshots"][0]["stage"] == "phase3"
