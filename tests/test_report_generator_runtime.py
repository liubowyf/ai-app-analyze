"""Runtime tests for report generator task helpers."""

import pytest

from modules.report_generator.generator import generate_analysis_report
from modules.report_generator.html_generator import HTMLReportGenerator
from workers.report_generator import _resolve_task_id


def test_resolve_task_id_accepts_string():
    assert _resolve_task_id("task-123") == "task-123"


def test_resolve_task_id_accepts_chain_result_dict():
    assert _resolve_task_id({"task_id": "task-456", "status": "success"}) == "task-456"


def test_resolve_task_id_rejects_invalid_input():
    with pytest.raises(ValueError):
        _resolve_task_id({"status": "success"})


def test_generate_analysis_report_exposes_dynamic_evidence_quality():
    report = generate_analysis_report(
        task_data={
            "id": "task-1",
            "package_name": "demo.apk",
            "apk_file_size": 100,
            "apk_md5": "abc",
            "apk_sha256": "def",
        },
        static_result=None,
        dynamic_result={
            "quality_gate": {
                "degraded": True,
                "reason": "empty_dynamic_evidence",
                "network_count": 0,
                "domains_count": 0,
                "screenshots_count": 0,
            }
        },
        network_requests=[],
        screenshots=[],
    )

    assert report["evidence_quality"]["degraded"] is True
    assert report["evidence_quality"]["reason"] == "empty_dynamic_evidence"


def test_web_report_renders_degraded_evidence_banner():
    generator = HTMLReportGenerator()
    html = generator.generate_web_report(
        {
            "package_name": "demo.apk",
            "risk_level": "low",
            "version": "1.0.0",
            "file_size": 100,
            "md5": "abc",
            "static_analysis": {"basic_info": {}},
            "screenshots": [],
            "network_requests": [],
            "dynamic_analysis_result": {},
            "evidence_quality": {
                "degraded": True,
                "reason": "empty_dynamic_evidence",
            },
            "master_domains": [],
        }
    )

    assert "empty_dynamic_evidence" in html
