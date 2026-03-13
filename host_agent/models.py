"""Pydantic models for the redroid host agent."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class SlotInfo(BaseModel):
    slot_name: str
    container_name: str
    adb_serial: str
    healthy: bool
    container_ip: Optional[str] = None
    detail: Optional[str] = None


class SlotListResponse(BaseModel):
    items: list[SlotInfo]


class CaptureCreateRequest(BaseModel):
    task_id: str
    slot_name: str


class CaptureSessionResponse(BaseModel):
    capture_id: str
    status: str
    task_id: Optional[str] = None
    slot_name: Optional[str] = None
    container_name: Optional[str] = None
    container_ip: Optional[str] = None
    pcap_path: Optional[str] = None
    text_path: Optional[str] = None
    zeek_dir: Optional[str] = None
    pcap_exists: Optional[bool] = None
    pcap_size: Optional[int] = None


class CaptureFileItem(BaseModel):
    name: str
    size: int


class CaptureFileListResponse(BaseModel):
    items: list[CaptureFileItem]
