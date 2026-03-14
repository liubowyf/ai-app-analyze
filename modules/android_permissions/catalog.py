"""Android permission catalog helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from models.analysis_tables import AnalysisRunTable, AndroidPermissionCatalogTable


CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "android_permission_catalog.json"
)


def _is_permission_code(value: str) -> bool:
    code = str(value or "").strip()
    return bool(code) and "." in code and "=" not in code and " " not in code


def _normalize_permission_codes(codes: list[str] | set[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in codes:
        code = str(item or "").strip()
        if not _is_permission_code(code) or code in seen:
            continue
        seen.add(code)
        result.append(code)
    result.sort()
    return result


@lru_cache(maxsize=1)
def load_permission_catalog_seed() -> dict[str, dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return {}

    try:
        rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip()
        if not code:
            continue
        result[code] = {
            "code": code,
            "description_en": row.get("description_en"),
            "description_zh": row.get("description_zh"),
            "source_url": row.get("source_url"),
        }
    return result


def aggregate_permission_summary_from_runs(
    runs: list[AnalysisRunTable],
) -> dict[str, list[str]]:
    requested: set[str] = set()
    granted: set[str] = set()
    failed: set[str] = set()

    for row in runs:
        details = row.details if isinstance(row.details, dict) else {}
        summary = details.get("permission_summary")
        if not isinstance(summary, dict):
            continue
        for item in summary.get("requested_permissions") or []:
            if isinstance(item, str) and _is_permission_code(item):
                requested.add(item)
        for item in summary.get("granted_permissions") or []:
            if isinstance(item, str) and _is_permission_code(item):
                granted.add(item)
        for item in summary.get("failed_permissions") or []:
            if isinstance(item, str) and _is_permission_code(item):
                failed.add(item)

    return {
        "requested_permissions": sorted(requested),
        "granted_permissions": sorted(granted),
        "failed_permissions": sorted(failed),
    }


def build_permission_details(
    db: Session,
    codes: list[str] | set[str] | tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    normalized_codes = _normalize_permission_codes(codes)
    if not normalized_codes:
        return {}

    result: dict[str, dict[str, Any]] = {}

    table_exists = False
    try:
        bind = db.get_bind()
        if bind is not None:
            inspector = inspect(bind)
            table_exists = "android_permission_catalog" in inspector.get_table_names()
    except Exception:
        table_exists = False

    if table_exists:
        rows = (
            db.query(AndroidPermissionCatalogTable)
            .filter(AndroidPermissionCatalogTable.code.in_(normalized_codes))
            .all()
        )
        for row in rows:
            result[row.code] = {
                "code": row.code,
                "description_en": row.description_en,
                "description_zh": row.description_zh,
                "source_url": row.source_url,
            }

    seed = load_permission_catalog_seed()
    for code in normalized_codes:
        if code in result:
            continue
        seed_row = seed.get(code)
        if seed_row:
            result[code] = dict(seed_row)
            continue
        result[code] = {
            "code": code,
            "description_en": None,
            "description_zh": None,
            "source_url": None,
        }

    return result
