import pytest
from modules.report_generator.html_generator import HTMLReportGenerator


def test_html_generator_init():
    """测试HTML生成器初始化"""
    generator = HTMLReportGenerator()
    assert generator.template_dir == "templates"


def test_generate_web_report():
    """测试生成在线版HTML报告"""
    generator = HTMLReportGenerator()
    data = {"task_id": "test", "package_name": "test.app"}
    html = generator.generate_web_report(data)
    assert "<html" in html
    assert "test.app" in html


def test_generate_static_report():
    """测试生成静态版HTML报告"""
    generator = HTMLReportGenerator()
    data = {"task_id": "test", "package_name": "test.app"}
    html = generator.generate_static_report(data)
    assert "<html" in html
    assert "test.app" in html
    # 静态版应该包含内联样式
    assert "<style>" in html