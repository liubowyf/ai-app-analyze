"""Schemas for frontend-oriented API responses."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class FrontendRiskLevel(str, Enum):
    """Stable frontend risk levels."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FrontendTaskListItem(BaseModel):
    """Task row tailored for frontend list rendering."""

    id: str
    app_name: str
    package_name: Optional[str] = None
    apk_file_name: str
    apk_file_size: int
    apk_md5: str
    status: str
    risk_level: FrontendRiskLevel
    created_at: str
    completed_at: Optional[str] = None
    report_ready: bool
    report_url: Optional[str] = None


class FrontendPagination(BaseModel):
    """Page-based pagination metadata."""

    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class FrontendTaskListResponse(BaseModel):
    """Frontend task list response."""

    items: List[FrontendTaskListItem]
    pagination: FrontendPagination


class FrontendReportTask(BaseModel):
    """Task header data for frontend report rendering."""

    id: str
    app_name: str
    package_name: Optional[str] = None
    apk_file_name: str
    apk_file_size: int
    apk_md5: str
    status: str
    risk_level: FrontendRiskLevel
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class FrontendReportSummary(BaseModel):
    """High-level report summary text."""

    risk_level: FrontendRiskLevel
    risk_label: str
    conclusion: str
    highlights: List[str]


class FrontendReportEvidenceSummary(BaseModel):
    """Top-level counts shown on the report page."""

    domains_count: int
    network_requests_count: int
    screenshots_count: int


class FrontendReportDomainItem(BaseModel):
    """Frontend domain clue item."""

    id: str
    domain: Optional[str] = None
    ip: Optional[str] = None
    score: int
    confidence: Optional[str] = None
    request_count: int
    post_count: int


class FrontendReportRequestItem(BaseModel):
    """Frontend network request item."""

    id: str
    host: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    response_code: Optional[int] = None
    request_time: Optional[str] = None


class FrontendReportScreenshotItem(BaseModel):
    """Frontend screenshot item using URL references."""

    id: str
    image_url: Optional[str] = None
    file_size: int
    stage: Optional[str] = None
    description: Optional[str] = None
    captured_at: Optional[str] = None


class FrontendReportResponse(BaseModel):
    """Frontend report response."""

    task: FrontendReportTask
    summary: FrontendReportSummary
    evidence_summary: FrontendReportEvidenceSummary
    domains: List[FrontendReportDomainItem]
    requests: List[FrontendReportRequestItem]
    screenshots: List[FrontendReportScreenshotItem]
    download_url: Optional[str] = None
