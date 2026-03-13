from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any


class HTMLReportGenerator:
    """HTML报告生成器"""

    # 翻译映射表
    RISK_LEVEL_MAP = {
        'high': '高风险',
        'medium': '中风险',
        'low': '低风险',
        'unknown': '未知风险'
    }

    CONFIDENCE_MAP = {
        'high': '高',
        'medium': '中',
        'low': '低'
    }

    EVIDENCE_MAP = {
        'data submission requests': '数据提交请求',
        'Contains sensitive user data': '包含敏感用户数据',
        'Uses non-encrypted connection': '使用非加密连接',
        'Uses non-standard port': '使用非标准端口',
        'Private IP address': '私有IP地址'
    }

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
        # 添加自定义过滤器
        self.env.filters['risk_level_cn'] = self._risk_level_cn
        self.env.filters['confidence_cn'] = self._confidence_cn
        self.env.filters['evidence_cn'] = self._evidence_cn

    @staticmethod
    def _risk_level_cn(value):
        """风险等级转中文"""
        return HTMLReportGenerator.RISK_LEVEL_MAP.get(value.lower(), value)

    @staticmethod
    def _confidence_cn(value):
        """置信度转中文"""
        return HTMLReportGenerator.CONFIDENCE_MAP.get(value.lower(), value)

    @staticmethod
    def _evidence_cn(value):
        """证据描述转中文"""
        result = value
        for en, cn in HTMLReportGenerator.EVIDENCE_MAP.items():
            result = result.replace(en, cn)
        return result

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