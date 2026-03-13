"""Report Generator module."""
from modules.report_generator.generator import ReportGenerator, generate_analysis_report
from modules.report_generator.html_generator import HTMLReportGenerator

__all__ = ["ReportGenerator", "generate_analysis_report", "HTMLReportGenerator"]
