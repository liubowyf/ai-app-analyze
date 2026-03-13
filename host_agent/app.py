"""FastAPI application for the redroid host agent."""

from __future__ import annotations

import secrets

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from core.config import settings
from host_agent.routers import captures, health, slots

app = FastAPI(
    title="Redroid Host Agent",
    version="0.1.0",
)


@app.middleware("http")
async def require_bearer_token(request, call_next):
    configured = str(settings.REDROID_HOST_AGENT_TOKEN or "").strip()
    if configured:
        auth = request.headers.get("authorization", "")
        expected = f"Bearer {configured}"
        if not secrets.compare_digest(auth, expected):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


app.include_router(health.router)
app.include_router(slots.router)
app.include_router(captures.router)
