"""Batch backfill utilities for historical IP geolocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from models.analysis_tables import MasterDomainTable, NetworkRequestTable
from modules.ip_geo.service import _normalize_ip_inputs, resolve_ip_locations


@dataclass
class IpGeoBackfillResult:
    batches: int = 0
    resolved_ips: int = 0
    updated_request_rows: int = 0
    updated_domain_rows: int = 0
    skipped_ips: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "batches": self.batches,
            "resolved_ips": self.resolved_ips,
            "updated_request_rows": self.updated_request_rows,
            "updated_domain_rows": self.updated_domain_rows,
            "skipped_ips": self.skipped_ips,
        }


def _collect_candidate_ips(
    db: Session,
    *,
    batch_size: int,
    task_id: str | None = None,
) -> tuple[list[str], int]:
    query_filters = [NetworkRequestTable.ip.is_not(None), NetworkRequestTable.ip_location.is_(None)]
    domain_filters = [MasterDomainTable.ip.is_not(None), MasterDomainTable.ip_location.is_(None)]
    if task_id:
        query_filters.append(NetworkRequestTable.task_id == task_id)
        domain_filters.append(MasterDomainTable.task_id == task_id)

    request_ips = [
        str(item[0]).strip()
        for item in db.query(NetworkRequestTable.ip)
        .filter(*query_filters)
        .limit(batch_size * 4)
        .all()
    ]
    domain_ips = [
        str(item[0]).strip()
        for item in db.query(MasterDomainTable.ip)
        .filter(*domain_filters)
        .limit(batch_size * 4)
        .all()
    ]

    normalized_pool = _normalize_ip_inputs([*request_ips, *domain_ips])
    collected: list[str] = []
    skipped = 0
    for ip in normalized_pool:
        collected.append(ip)
        if len(collected) >= batch_size:
            break

    total_distinct = len(normalized_pool)
    if total_distinct > len(collected):
        skipped = total_distinct - len(collected)
    return collected, skipped


def _apply_locations(
    db: Session,
    *,
    resolved: dict[str, str],
    task_id: str | None = None,
) -> tuple[int, int]:
    if not resolved:
        return 0, 0

    request_query = db.query(NetworkRequestTable).filter(
        NetworkRequestTable.ip.in_(tuple(resolved.keys())),
        NetworkRequestTable.ip_location.is_(None),
    )
    domain_query = db.query(MasterDomainTable).filter(
        MasterDomainTable.ip.in_(tuple(resolved.keys())),
        MasterDomainTable.ip_location.is_(None),
    )
    if task_id:
        request_query = request_query.filter(NetworkRequestTable.task_id == task_id)
        domain_query = domain_query.filter(MasterDomainTable.task_id == task_id)

    request_rows = request_query.all()
    domain_rows = domain_query.all()

    for row in request_rows:
        row.ip_location = resolved.get(str(row.ip).strip())
    for row in domain_rows:
        row.ip_location = resolved.get(str(row.ip).strip())

    if request_rows or domain_rows:
        db.commit()

    return len(request_rows), len(domain_rows)


def backfill_missing_ip_locations(
    db: Session,
    *,
    batch_size: int = 200,
    limit: int | None = None,
    task_id: str | None = None,
) -> dict[str, int]:
    result = IpGeoBackfillResult()
    remaining = None if limit is None else max(int(limit), 0)
    batch_size = max(1, int(batch_size))

    while remaining is None or remaining > 0:
        current_batch_size = batch_size if remaining is None else min(batch_size, remaining)
        candidate_ips, skipped = _collect_candidate_ips(
            db,
            batch_size=current_batch_size,
            task_id=task_id,
        )
        result.skipped_ips += skipped
        if not candidate_ips:
            break

        resolved = resolve_ip_locations(candidate_ips)
        if not resolved:
            break

        updated_request_rows, updated_domain_rows = _apply_locations(
            db,
            resolved=resolved,
            task_id=task_id,
        )

        result.batches += 1
        result.resolved_ips += len(resolved)
        result.updated_request_rows += updated_request_rows
        result.updated_domain_rows += updated_domain_rows

        if remaining is not None:
            remaining -= len(resolved)
            if remaining <= 0:
                break

    return result.as_dict()
