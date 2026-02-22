"""Stage run tracking helpers for analysis workers."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.analysis_tables import AnalysisRunTable


def ensure_analysis_run_table(db: Session) -> None:
    """Create analysis_runs table lazily for environments without migrations."""
    from core.database import Base, engine

    Base.metadata.create_all(bind=engine, tables=[AnalysisRunTable.__table__])


def _next_attempt(db: Session, task_id: str, stage: str) -> int:
    latest = (
        db.query(AnalysisRunTable)
        .filter(AnalysisRunTable.task_id == task_id, AnalysisRunTable.stage == stage)
        .order_by(AnalysisRunTable.attempt.desc(), AnalysisRunTable.started_at.desc())
        .first()
    )
    if not latest:
        return 1
    return int(latest.attempt or 0) + 1


def start_stage_run(
    db: Session,
    task_id: str,
    stage: str,
    emulator: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AnalysisRunTable:
    """Create one running stage record."""
    ensure_analysis_run_table(db)
    run = AnalysisRunTable(
        task_id=task_id,
        stage=stage,
        attempt=_next_attempt(db, task_id=task_id, stage=stage),
        status="running",
        worker_name=os.getenv("HOSTNAME") or "",
        emulator=emulator,
        details=details,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()
    return run


def update_stage_context(
    db: Session,
    task_id: str,
    stage: str,
    *,
    emulator: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Attach runtime context to latest running stage."""
    run = (
        db.query(AnalysisRunTable)
        .filter(
            AnalysisRunTable.task_id == task_id,
            AnalysisRunTable.stage == stage,
            AnalysisRunTable.status == "running",
        )
        .order_by(AnalysisRunTable.started_at.desc())
        .first()
    )
    if not run:
        return
    if emulator is not None:
        run.emulator = emulator
    if details is not None:
        run.details = details


def finish_stage_run(
    db: Session,
    task_id: str,
    stage: str,
    success: bool,
    error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Finish latest running stage and write duration."""
    run = (
        db.query(AnalysisRunTable)
        .filter(
            AnalysisRunTable.task_id == task_id,
            AnalysisRunTable.stage == stage,
            AnalysisRunTable.status == "running",
        )
        .order_by(AnalysisRunTable.started_at.desc())
        .first()
    )
    if not run:
        run = start_stage_run(db, task_id=task_id, stage=stage)

    completed_at = datetime.utcnow()
    run.completed_at = completed_at
    run.status = "success" if success else "failed"
    run.error_message = error_message if not success else None
    run.duration_seconds = max(
        0,
        int((completed_at - (run.started_at or completed_at)).total_seconds()),
    )
    if details is not None:
        run.details = details
