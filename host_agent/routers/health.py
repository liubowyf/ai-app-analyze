"""Health endpoints for the redroid host agent."""

from __future__ import annotations

from fastapi import APIRouter

from host_agent.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")
