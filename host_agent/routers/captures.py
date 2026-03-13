"""Capture lifecycle endpoints for the redroid host agent."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from core.config import settings
from host_agent.models import CaptureCreateRequest, CaptureFileListResponse, CaptureSessionResponse
from host_agent.services.capture_service import CaptureService
from host_agent.services.docker_runtime import DockerRuntime

router = APIRouter()


def get_docker_runtime() -> DockerRuntime:
    return DockerRuntime()


def get_capture_service() -> CaptureService:
    return CaptureService()


def _resolve_slot(slot_name: str, runtime: DockerRuntime) -> dict[str, object]:
    for slot in runtime.list_slots(settings.redroid_slots):
        if str(slot.get("slot_name") or "") == slot_name:
            return slot
    raise HTTPException(status_code=404, detail="slot_not_found")


@router.post("/captures", response_model=CaptureSessionResponse)
def create_capture(
    payload: CaptureCreateRequest,
    runtime: DockerRuntime = Depends(get_docker_runtime),
    service: CaptureService = Depends(get_capture_service),
) -> CaptureSessionResponse:
    slot = _resolve_slot(payload.slot_name, runtime)
    result = service.start_capture(
        task_id=payload.task_id,
        slot_name=payload.slot_name,
        container_name=str(slot.get("container_name") or ""),
        container_ip=str(slot.get("container_ip") or ""),
    )
    return CaptureSessionResponse(**result)


@router.get("/captures/{capture_id}", response_model=CaptureSessionResponse)
def get_capture(capture_id: str, service: CaptureService = Depends(get_capture_service)) -> CaptureSessionResponse:
    try:
        return CaptureSessionResponse(**service.get_capture(capture_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/captures/{capture_id}/stop", response_model=CaptureSessionResponse)
def stop_capture(capture_id: str, service: CaptureService = Depends(get_capture_service)) -> CaptureSessionResponse:
    try:
        return CaptureSessionResponse(**service.stop_capture(capture_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/captures/{capture_id}/analyze", response_model=CaptureSessionResponse)
def analyze_capture(capture_id: str, service: CaptureService = Depends(get_capture_service)) -> CaptureSessionResponse:
    try:
        return CaptureSessionResponse(**service.analyze_capture(capture_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/captures/{capture_id}/files", response_model=CaptureFileListResponse)
def list_capture_files(capture_id: str, service: CaptureService = Depends(get_capture_service)) -> CaptureFileListResponse:
    try:
        return CaptureFileListResponse(items=service.list_files(capture_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/captures/{capture_id}/files/{name}")
def download_capture_file(
    capture_id: str,
    name: str,
    service: CaptureService = Depends(get_capture_service),
) -> Response:
    try:
        content = service.read_file(capture_id, name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type="text/plain; charset=utf-8")


@router.delete("/captures/{capture_id}", response_model=CaptureSessionResponse)
def delete_capture(capture_id: str, service: CaptureService = Depends(get_capture_service)) -> CaptureSessionResponse:
    return CaptureSessionResponse(**service.delete_capture(capture_id))
