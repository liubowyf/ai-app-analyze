"""Slot inspection endpoints for the redroid host agent."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.config import settings
from host_agent.models import SlotListResponse
from host_agent.services.docker_runtime import DockerRuntime

router = APIRouter()


def get_docker_runtime() -> DockerRuntime:
    return DockerRuntime()


@router.get("/slots", response_model=SlotListResponse)
def list_slots(runtime: DockerRuntime = Depends(get_docker_runtime)) -> SlotListResponse:
    return SlotListResponse(items=runtime.list_slots(settings.redroid_slots))
