"""Report Generator module for PDF report generation."""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

logger = logging.getLogger(__name__)

# Default template directory
TEMPLATE_DIR = "templates"


def _normalize_int(value: Any) -> int:
    """Normalize unknown values to non-negative ints for report stats."""
    try:
        return max(0, int(value))
    except Exception:
        return 0


def _extract_evidence_quality(
    dynamic_result: Optional[Dict[str, Any]],
    network_requests: Optional[list],
    screenshots: Optional[list],
) -> Dict[str, Any]:
    """Extract dynamic evidence quality gate from dynamic result payload."""
    quality_gate = {}
    if isinstance(dynamic_result, dict):
        gate_raw = dynamic_result.get("quality_gate")
        if isinstance(gate_raw, dict):
            quality_gate = gate_raw

    network_count = _normalize_int(quality_gate.get("network_count", len(network_requests or [])))
    domains_count = _normalize_int(quality_gate.get("domains_count", 0))
    screenshots_count = _normalize_int(quality_gate.get("screenshots_count", len(screenshots or [])))
    degraded = bool(
        quality_gate.get("degraded", network_count == 0 and domains_count == 0 and screenshots_count == 0)
    )
    reason = quality_gate.get("reason")
    if degraded and not reason:
        reason = "empty_dynamic_evidence"
    return {
        "degraded": degraded,
        "reason": reason,
        "network_count": network_count,
        "domains_count": domains_count,
        "screenshots_count": screenshots_count,
    }


class ReportGenerator:
    """PDF report generator using Jinja2 and WeasyPrint."""

    def __init__(self, template_dir: str = TEMPLATE_DIR):
        """
        Initialize report generator.

        Args:
            template_dir: Directory containing Jinja2 templates
        """
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_html(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render HTML from template.

        Args:
            template_name: Template file name
            context: Template context data

        Returns:
            Rendered HTML string
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template: {e}")
            raise

    def generate_pdf(self, html_content: str, output_path: str) -> bool:
        """
        Generate PDF from HTML content.

        Args:
            html_content: HTML content string
            output_path: Output PDF file path

        Returns:
            True if successful
        """
        try:
            HTML(string=html_content).write_pdf(output_path)
            logger.info(f"Generated PDF: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            return False

    def generate_report(self, analysis_data: Dict[str, Any],
                      template_name: str = "report.html",
                      output_path: Optional[str] = None) -> Optional[str]:
        """
        Generate complete analysis report.

        Args:
            analysis_data: Analysis data dictionary
            template_name: Template to use
            output_path: Optional output path (returns PDF bytes if None)

        Returns:
            PDF path or None on failure
        """
        # Add metadata to context
        context = {
            **analysis_data,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_title": f"APK Analysis Report - {analysis_data.get('package_name', 'Unknown')}",
        }

        # Render HTML
        html_content = self.render_html(template_name, context)

        if output_path:
            # Save to file
            self.generate_pdf(html_content, output_path)
            return output_path
        else:
            # Return as bytes
            from io import BytesIO
            pdf_buffer = BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            return pdf_buffer.getvalue()


def generate_analysis_report(task_data: Dict[str, Any],
                           static_result: Optional[Dict[str, Any]] = None,
                           dynamic_result: Optional[Dict[str, Any]] = None,
                           network_requests: Optional[list] = None,
                           screenshots: Optional[list] = None) -> Dict[str, Any]:
    """
    Generate complete analysis report data structure.

    Args:
        task_data: Task information
        static_result: Static analysis results
        dynamic_result: Dynamic analysis results
        network_requests: List of network requests
        screenshots: List of screenshots

    Returns:
        Report data dictionary
    """
    # Calculate risk level
    risk_factors = []
    risk_score = 0

    if static_result:
        # Check permissions
        permissions = static_result.get("permissions", [])
        dangerous_perms = [p for p in permissions if p.get("risk_level") in ("high", "critical")]
        if dangerous_perms:
            risk_factors.append(f"Requests {len(dangerous_perms)} dangerous permissions")
            risk_score += len(dangerous_perms) * 10

        # Check exported components
        components = static_result.get("components", [])
        exported = [c for c in components if c.get("is_exported")]
        if exported:
            risk_factors.append(f"Has {len(exported)} exported components")
            risk_score += len(exported) * 5

    if dynamic_result:
        # Check network activity
        if network_requests:
            risk_factors.append(f"Made {len(network_requests)} network requests")
            risk_score += len(network_requests) * 2
    evidence_quality = _extract_evidence_quality(dynamic_result, network_requests, screenshots)
    if evidence_quality["degraded"]:
        risk_factors.append(f"Dynamic evidence degraded ({evidence_quality['reason']})")

    # Determine risk level
    if risk_score >= 50:
        risk_level = "high"
    elif risk_score >= 20:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "task_id": task_data.get("id"),
        "package_name": task_data.get("package_name", static_result.get("basic_info", {}).get("package_name") if static_result else "Unknown"),
        "version": static_result.get("basic_info", {}).get("version_name") if static_result else "Unknown",
        "file_size": task_data.get("apk_file_size"),
        "md5": task_data.get("apk_md5"),
        "sha256": task_data.get("apk_sha256"),
        "static_analysis": static_result,
        "dynamic_analysis": dynamic_result,
        "dynamic_analysis_result": dynamic_result,
        "network_requests": network_requests or [],
        "screenshots": screenshots or [],
        "evidence_quality": evidence_quality,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "summary": _generate_summary(risk_level, risk_factors),
    }


def _generate_summary(risk_level: str, risk_factors: list) -> str:
    """Generate summary text based on risk analysis."""
    if risk_level == "high":
        summary = "This application has been flagged as HIGH risk. "
    elif risk_level == "medium":
        summary = "This application has been flagged as MEDIUM risk. "
    else:
        summary = "This application appears to be LOW risk. "

    if risk_factors:
        summary += "Key risk factors: " + "; ".join(risk_factors) + "."

    return summary
