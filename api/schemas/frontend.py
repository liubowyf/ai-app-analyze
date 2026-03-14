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
    icon_url: Optional[str] = None
    retryable: bool = False
    deletable: bool = True
    failure_reason: Optional[str] = None
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


class FrontendRuntimeStatusSlot(BaseModel):
    slot_name: str
    container_name: str
    healthy: bool
    busy: bool
    holder_task_id: Optional[str] = None
    detail: Optional[str] = None


class FrontendRuntimeStatusTasks(BaseModel):
    queued_count: int
    static_running_count: int
    dynamic_running_count: int
    report_running_count: int
    running_count: int


class FrontendRuntimeStatusRedroid(BaseModel):
    configured_slots: int
    healthy_slots: int
    busy_slots: int
    slots: List[FrontendRuntimeStatusSlot]


class FrontendRuntimeStatusResponse(BaseModel):
    api_healthy: bool
    worker_ready: bool
    queue_backend: str
    tasks: FrontendRuntimeStatusTasks
    redroid: FrontendRuntimeStatusRedroid
    checked_at: str


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
    ips_count: int
    observation_hits: int
    capture_mode: Optional[str] = None
    screenshots_count: int


class FrontendReportDomainItem(BaseModel):
    """Frontend domain clue item."""

    id: str
    domain: Optional[str] = None
    ip: Optional[str] = None
    ip_location: Optional[str] = None
    score: int
    confidence: Optional[str] = None
    hit_count: int
    request_count: int
    post_count: int
    unique_ip_count: int = 0
    source_types: List[str] = []
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    relevance_score: Optional[int] = None
    relevance_level: Optional[str] = None
    reasons: List[str] = []
    is_common_infra: bool = False
    infra_category: Optional[str] = None


class FrontendReportIpItem(BaseModel):
    """Frontend suspected IP item."""

    ip: str
    ip_location: Optional[str] = None
    hit_count: int
    domain_count: int
    primary_domain: Optional[str] = None
    source_types: List[str] = []
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    relevance_score: Optional[int] = None
    relevance_level: Optional[str] = None
    reasons: List[str] = []
    is_common_infra: bool = False
    infra_category: Optional[str] = None


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
    top_domains: List[FrontendReportDomainItem]
    top_ips: List[FrontendReportIpItem]
    public_domains: List[FrontendReportDomainItem]
    public_ips: List[FrontendReportIpItem]
    screenshots: List[FrontendReportScreenshotItem]
    download_url: Optional[str] = None
