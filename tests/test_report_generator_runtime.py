"""Runtime tests for report generator task helpers."""

import base64
import pytest

from modules.frontend_presenters.report import FrontendReportScreenshotSource
from modules.report_generator.generator import generate_analysis_report
from modules.report_generator.html_generator import HTMLReportGenerator
from workers.report_generator import _build_report_context_for_stage, _resolve_task_id


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


def test_build_report_context_for_stage_uses_frontend_report_contract(monkeypatch):
    monkeypatch.setattr(
        "workers.report_generator.build_frontend_report_download_context",
        lambda db, task_id, require_completed=False: {
            "task": {"id": task_id, "app_name": "征途国际"},
            "summary": {
                "risk_level": "medium",
                "risk_label": "中风险",
                "conclusion": "测试结论",
                "highlights": [],
            },
            "evidence_summary": {
                "domains_count": 2,
                "ips_count": 1,
                "observation_hits": 3,
                "capture_mode": "redroid_zeek",
                "screenshots_count": 1,
                "source_breakdown": {"connect": 3},
            },
            "screenshots": [{"id": "shot-1"}],
            "top_domains": [],
            "top_ips": [],
            "timeline": [],
        },
    )
    monkeypatch.setattr(
        "workers.report_generator.resolve_frontend_report_screenshot_source",
        lambda db, task_id, screenshot_ref, require_completed=False: FrontendReportScreenshotSource(
            storage_path="screens/task/shot-1.png"
        ),
    )
    monkeypatch.setattr(
        "workers.report_generator.storage_client.download_file",
        lambda storage_path: b"png-bytes",
    )

    context = _build_report_context_for_stage(object(), "task-1")

    assert context["summary"]["conclusion"] == "测试结论"
    assert context["screenshots"][0]["storage_path"] == "screens/task/shot-1.png"
    assert context["screenshots"][0]["image_base64"] == base64.b64encode(b"png-bytes").decode("utf-8")


def test_build_report_context_for_stage_raises_when_task_missing(monkeypatch):
    monkeypatch.setattr(
        "workers.report_generator.build_frontend_report_download_context",
        lambda db, task_id, require_completed=False: None,
    )

    with pytest.raises(ValueError):
        _build_report_context_for_stage(object(), "missing-task")


def test_build_report_context_for_stage_raises_when_dynamic_evidence_missing(monkeypatch):
    monkeypatch.setattr(
        "workers.report_generator.build_frontend_report_download_context",
        lambda db, task_id, require_completed=False: {
            "task": {"id": task_id, "app_name": "仅静态任务"},
            "summary": {
                "risk_level": "unknown",
                "risk_label": "待确认",
                "conclusion": "仅静态信息",
                "highlights": [],
            },
            "evidence_summary": {
                "domains_count": 0,
                "ips_count": 0,
                "observation_hits": 0,
                "capture_mode": None,
                "screenshots_count": 0,
                "source_breakdown": {},
            },
            "screenshots": [],
            "top_domains": [],
            "top_ips": [],
            "timeline": [],
        },
    )

    with pytest.raises(ValueError, match="Dynamic analysis evidence missing"):
        _build_report_context_for_stage(object(), "task-static-only")
