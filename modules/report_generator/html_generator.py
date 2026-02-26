from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any


class HTMLReportGenerator:
    """HTML报告生成器"""

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate_web_report(self, data: Dict[str, Any]) -> str:
        """生成在线版HTML报告"""
        template = self.env.get_template("report_web.html")
        return template.render(**data)

    def generate_static_report(self, data: Dict[str, Any]) -> str:
        """生成静态版HTML报告（内联资源）"""
        template = self.env.get_template("report_static.html")
        html = template.render(**data)
        return self._inline_resources(html)

    def _inline_resources(self, html: str) -> str:
        """内联CSS和JS资源"""
        # 基础实现，后续可扩展为真正的资源内联
        return html