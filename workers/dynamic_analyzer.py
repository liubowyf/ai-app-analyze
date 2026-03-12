"""Dynamic analysis stage service."""
import json
import logging
import re
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any
import os
import time

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from core.config import settings
from core.database import SessionLocal
from core.storage import storage_client
from models.analysis_tables import (
    DynamicAnalysisTable,
    MasterDomainTable,
    NetworkRequestTable,
    ScreenshotTable,
)
from models.task import Task, TaskStatus
from modules.android_runner import AndroidRunner
from modules.traffic_monitor import android_proxy_runtime
from modules.task_orchestration.run_tracker import (
    finish_stage_run,
)

logger = logging.getLogger(__name__)

MAX_DB_PAYLOAD_BYTES = 3_500_000  # keep below typical 4MB MySQL packet limit
MAX_DB_SCREENSHOTS = 25
MAX_DB_REQUESTS = 1000
MAX_SCREENSHOT_DESCRIPTION_LENGTH = 255
DEFAULT_CAPTURE_MODE = "redroid_zeek"


def _commit_with_retry(db: Session, retries: int = 2, delay: float = 1.0, context: str = "") -> None:
    """Commit session with rollback/retry on transient DB disconnect."""
    for attempt in range(retries + 1):
        try:
            db.commit()
            return
        except OperationalError as exc:
            db.rollback()
            if attempt >= retries:
                raise
            logger.warning(
                "DB commit failed (%s), retrying %s/%s: %s",
                context or "unknown",
                attempt + 1,
                retries,
                exc,
            )
            time.sleep(delay)


def _mark_task_failed(task_id: str, error_message: str) -> None:
    """Best-effort persist failed status in a fresh DB session."""
    fail_db: Session = SessionLocal()
    try:
        failed_task = fail_db.query(Task).filter(Task.id == task_id).first()
        if not failed_task:
            return
        failed_task.status = TaskStatus.FAILED
        failed_task.error_message = error_message
        finish_stage_run(
            fail_db,
            task_id=task_id,
            stage="dynamic",
            success=False,
            error_message=error_message,
        )
        _commit_with_retry(fail_db, context="mark_task_failed")
    except Exception as exc:
        logger.error("Failed to persist task failure status for %s: %s", task_id, exc)
    finally:
        fail_db.close()


def _get_static_package_name(static_analysis_result: Optional[Dict]) -> Optional[str]:
    """Extract package name from legacy or nested static analysis payloads."""
    if not isinstance(static_analysis_result, dict):
        return None
    return (
        static_analysis_result.get("package_name")
        or static_analysis_result.get("basic_info", {}).get("package_name")
    )


def _compact_screenshots(screenshots: list, max_items: int) -> list:
    """Drop heavy base64 payload from DB JSON and keep storage metadata."""
    compacted = []
    for shot in screenshots[:max_items]:
        compacted.append(
            {
                "stage": shot.get("stage"),
                "description": shot.get("description"),
                "timestamp": shot.get("timestamp"),
                "storage_path": shot.get("storage_path"),
            }
        )
    return compacted


def _build_dynamic_result(exploration_result, traffic_monitor, domain_report, max_screenshots: int, max_requests: int) -> dict:
    """Build DB-safe dynamic result payload."""
    network_analysis = traffic_monitor.analyze_traffic()
    capture_mode = str(
        network_analysis.get("capture_mode")
        or getattr(traffic_monitor, "capture_mode", DEFAULT_CAPTURE_MODE)
        or DEFAULT_CAPTURE_MODE
    )
    network_analysis.setdefault("capture_mode", capture_mode)
    network_analysis.setdefault(
        "capture_diagnostics",
        getattr(traffic_monitor, "get_capture_diagnostics", lambda: {"capture_mode": capture_mode})(),
    )
    return {
        "capture_mode": capture_mode,
        "exploration_result": {
            "total_steps": exploration_result.total_steps,
            "screenshots": _compact_screenshots(exploration_result.screenshots, max_screenshots),
            "activities_visited": exploration_result.activities_visited,
            "success": exploration_result.success,
            "error_message": exploration_result.error_message,
            "phases_completed": exploration_result.phases_completed,
            "history": exploration_result.history[-300:],
        },
        "network_analysis": network_analysis,
        "suspicious_requests": traffic_monitor.get_requests_as_dict()[:max_requests],
        "candidate_requests": traffic_monitor.get_candidate_requests_as_dict()[:max_requests],
        "network_aggregated": traffic_monitor.get_aggregated_requests()[:200],
        "candidate_aggregated": traffic_monitor.get_candidate_aggregated_requests()[:200],
        "master_domains": domain_report,
    }


def _build_dynamic_quality_gate(
    screenshot_count: int,
    primary_request_count: int,
    candidate_request_count: int,
    master_domain_count: int,
) -> dict[str, Any]:
    """Build quality gate result for dynamic evidence completeness."""
    screenshots_count = max(0, int(screenshot_count or 0))
    primary_count = max(0, int(primary_request_count or 0))
    candidate_count = max(0, int(candidate_request_count or 0))
    domains_count = max(0, int(master_domain_count or 0))
    network_count = primary_count + candidate_count
    degraded = network_count == 0 and domains_count == 0 and screenshots_count == 0
    return {
        "degraded": degraded,
        "reason": "empty_dynamic_evidence" if degraded else None,
        "network_count": network_count,
        "domains_count": domains_count,
        "screenshots_count": screenshots_count,
    }


def _safe_parse_datetime(value: Any) -> Optional[datetime]:
    """Parse datetime from heterogeneous payload values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


def _truncate_screenshot_description(description: Any) -> Optional[str]:
    """Keep screenshot description within DB column width."""
    if description is None:
        return None
    text = str(description)
    if len(text) <= MAX_SCREENSHOT_DESCRIPTION_LENGTH:
        return text
    return text[:MAX_SCREENSHOT_DESCRIPTION_LENGTH]


def _observation_value(item: Any, *keys: str) -> Any:
    """Read observation values from object or dict payloads."""
    for key in keys:
        if isinstance(item, dict):
            value = item.get(key)
        else:
            value = getattr(item, key, None)
        if value not in (None, ""):
            return value
    return None


def _merge_source_breakdown(*groups: Any) -> dict[str, int]:
    """Combine source counters from primary and candidate pools."""
    merged: dict[str, int] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        for key, value in group.items():
            try:
                count = int(value or 0)
            except Exception:
                continue
            merged[str(key)] = merged.get(str(key), 0) + count
    return merged


def _build_dynamic_stage_run_details(
    *,
    emulator: Optional[Dict[str, Any]],
    exploration_result: Any,
    primary_requests: list[Any],
    candidate_requests: list[Any],
    master_domains: list[Any],
    quality_gate: dict[str, Any],
    network_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Build analysis_runs.details using no-mitm concurrency and observation semantics."""
    observations = list(primary_requests or []) + list(candidate_requests or [])
    observed_domains = {
        str(domain).strip().lower()
        for domain in (_observation_value(item, "host", "domain") for item in observations)
        if domain
    }
    observed_ips = {
        str(ip).strip()
        for ip in (_observation_value(item, "ip") for item in observations)
        if ip
    }
    observation_hits = 0
    for item in observations:
        try:
            observation_hits += max(1, int(_observation_value(item, "hit_count", "count") or 1))
        except Exception:
            observation_hits += 1

    return {
        "capture_mode": str(network_analysis.get("capture_mode") or DEFAULT_CAPTURE_MODE),
        "lease_scope": "emulator_only",
        "resource_wait": "emulator_lease",
        "emulator_lease_backend": (emulator or {}).get("lease_backend", "unknown"),
        "observed_domains": len(observed_domains),
        "observed_ips": len(observed_ips),
        "observation_hits": observation_hits,
        "source_breakdown": _merge_source_breakdown(
            network_analysis.get("sources"),
            network_analysis.get("candidate_sources"),
        ),
        "steps": int(getattr(exploration_result, "total_steps", 0) or 0),
        "primary_requests": len(primary_requests or []),
        "candidate_requests": len(candidate_requests or []),
        "master_domains": len(master_domains or []),
        "degraded": bool(quality_gate.get("degraded")),
        "degraded_reason": quality_gate.get("reason"),
    }


def _persist_dynamic_normalized_tables(
    db: Session,
    task_id: str,
    package_name: Optional[str],
    exploration_result: Any,
    traffic_monitor: Any,
    domain_report: Dict[str, Any],
) -> None:
    """
    Persist dynamic outputs into normalized tables for downstream API queries.

    Any persistence issue is downgraded to warning and should not fail the task.
    """
    try:
        # Lightweight guard for deployments that have not run migrations yet.
        from core.database import Base, engine

        Base.metadata.create_all(
            bind=engine,
            tables=[
                DynamicAnalysisTable.__table__,
                NetworkRequestTable.__table__,
                MasterDomainTable.__table__,
                ScreenshotTable.__table__,
            ],
        )

        primary_requests = traffic_monitor.get_requests_as_dict()
        candidate_requests = traffic_monitor.get_candidate_requests_as_dict()
        all_requests = primary_requests + candidate_requests
        network_analysis = getattr(traffic_monitor, "analyze_traffic", lambda: {})()
        source_breakdown = {}
        if isinstance(network_analysis, dict):
            breakdown_raw = network_analysis.get("source_breakdown")
            if isinstance(breakdown_raw, dict):
                source_breakdown = {
                    str(key): int(value or 0)
                    for key, value in breakdown_raw.items()
                }
        capture_mode = str(network_analysis.get("capture_mode") or DEFAULT_CAPTURE_MODE)

        def _sum_hits(rows: list[dict[str, Any]]) -> int:
            total = 0
            for row in rows:
                try:
                    total += max(1, int(row.get("hit_count") or row.get("count") or 1))
                except Exception:
                    total += 1
            return total

        total_observation_hits = _sum_hits(all_requests)
        primary_observation_hits = _sum_hits(primary_requests)
        candidate_observation_hits = _sum_hits(candidate_requests)
        unique_domains = {
            (item.get("host") or item.get("domain") or "").strip().lower()
            for item in all_requests
            if item.get("host") or item.get("domain")
        }
        unique_ips = {
            (item.get("ip") or "").strip()
            for item in all_requests
            if item.get("ip")
        }
        domain_stats_rows = getattr(traffic_monitor, "get_domain_stats", lambda: [])()
        domain_stats_index = {
            str(item.get("domain")).strip().lower(): item
            for item in domain_stats_rows
            if isinstance(item, dict) and item.get("domain")
        }

        # Ensure idempotency for retries.
        db.query(NetworkRequestTable).filter(NetworkRequestTable.task_id == task_id).delete(synchronize_session=False)
        db.query(MasterDomainTable).filter(MasterDomainTable.task_id == task_id).delete(synchronize_session=False)
        db.query(ScreenshotTable).filter(ScreenshotTable.task_id == task_id).delete(synchronize_session=False)
        db.query(DynamicAnalysisTable).filter(DynamicAnalysisTable.task_id == task_id).delete(synchronize_session=False)

        dynamic_row = DynamicAnalysisTable(
            task_id=task_id,
            total_steps=int(getattr(exploration_result, "total_steps", 0) or 0),
            phases_completed=",".join(getattr(exploration_result, "phases_completed", []) or []),
            unique_activities=len(set(getattr(exploration_result, "activities_visited", []) or [])),
            activities_list=json.dumps(getattr(exploration_result, "activities_visited", []) or [], ensure_ascii=False),
            total_screenshots=len(getattr(exploration_result, "screenshots", []) or []),
            total_requests=len(all_requests),
            total_observations=total_observation_hits,
            unique_domains=len(unique_domains),
            unique_ips=len(unique_ips),
            master_domains=len((domain_report or {}).get("master_domains", []) or []),
            primary_observations=primary_observation_hits,
            candidate_observations=candidate_observation_hits,
            capture_mode=capture_mode,
            source_breakdown=source_breakdown or None,
            success=1 if getattr(exploration_result, "success", False) else 0,
            error_message=getattr(exploration_result, "error_message", None),
            detected_package=package_name,
            started_at=None,
            completed_at=datetime.utcnow(),
            duration_seconds=0,
        )
        db.add(dynamic_row)

        for item in (primary_requests + candidate_requests)[:3000]:
            db.add(
                NetworkRequestTable(
                    task_id=task_id,
                    url=item.get("url"),
                    method=item.get("method"),
                    host=item.get("host") or item.get("domain"),
                    path=item.get("path"),
                    ip=item.get("ip"),
                    port=int(item.get("port") or 80),
                    scheme=item.get("scheme"),
                    response_code=item.get("response_code"),
                    content_type=item.get("content_type"),
                    request_size=0,
                    response_size=0,
                    request_time=_safe_parse_datetime(item.get("request_time") or item.get("first_seen_at")),
                    first_seen_at=_safe_parse_datetime(item.get("first_seen_at") or item.get("request_time")),
                    last_seen_at=_safe_parse_datetime(item.get("last_seen_at") or item.get("request_time")),
                    hit_count=max(1, int(item.get("hit_count") or item.get("count") or 1)),
                    source_type=item.get("source_type") or item.get("source") or "unknown",
                    transport=item.get("transport"),
                    protocol=item.get("protocol"),
                    capture_mode=item.get("capture_mode") or capture_mode,
                    attribution_tier=item.get("attribution_tier") or "primary",
                    package_name=item.get("package_name"),
                    uid=item.get("uid"),
                    process_name=item.get("process_name"),
                    attribution_confidence=item.get("attribution_confidence"),
                    has_sensitive_data=0,
                    sensitive_types=None,
                )
            )

        for row in (domain_report or {}).get("master_domains", []) or []:
            evidence = row.get("evidence")
            evidence_text = json.dumps(evidence, ensure_ascii=False) if evidence is not None else None
            stats_row = domain_stats_index.get(str(row.get("domain") or "").strip().lower(), {})
            db.add(
                MasterDomainTable(
                    task_id=task_id,
                    domain=row.get("domain"),
                    ip=row.get("ip"),
                    confidence_score=int(row.get("score", 0) or 0),
                    confidence_level=row.get("confidence"),
                    evidence=evidence_text,
                    request_count=int(
                        row.get("hit_count")
                        or row.get("request_count", 0)
                        or stats_row.get("hit_count", 0)
                        or 0
                    ),
                    post_count=int(row.get("post_count", 0) or 0),
                    first_seen_at=_safe_parse_datetime(row.get("first_seen_at") or stats_row.get("first_seen_at")),
                    last_seen_at=_safe_parse_datetime(row.get("last_seen_at") or stats_row.get("last_seen_at")),
                    unique_ip_count=int(
                        row.get("unique_ip_count", 0)
                        or stats_row.get("unique_ip_count", 0)
                        or 0
                    ),
                    source_types_json=(
                        row.get("source_types")
                        or row.get("source_types_json")
                        or stats_row.get("source_types")
                    ),
                    capture_mode=row.get("capture_mode") or stats_row.get("capture_mode") or capture_mode,
                )
            )

        for shot in (getattr(exploration_result, "screenshots", []) or [])[:300]:
            storage_path = shot.get("storage_path")
            stage = shot.get("stage")
            description = _truncate_screenshot_description(shot.get("description"))
            captured_at = _safe_parse_datetime(shot.get("timestamp")) or datetime.utcnow()
            db.add(
                ScreenshotTable(
                    task_id=task_id,
                    storage_path=storage_path,
                    file_size=0,
                    stage=stage,
                    description=description,
                    captured_at=captured_at,
                )
            )
    except Exception as exc:
        logger.warning("Persist normalized dynamic tables failed task=%s: %s", task_id, exc)



def _detect_package_name(apk_path: str) -> Optional[str]:
    """Best-effort package detection from APK."""
    package: Optional[str] = None
    try:
        from androguard.misc import AnalyzeAPK

        a, _, _ = AnalyzeAPK(apk_path)
        package = a.get_package()
        if isinstance(package, str) and package.strip():
            return package.strip()
    except Exception as exc:
        logger.warning("Failed to detect package name from APK: %s", exc)

    for cmd in (
        ["aapt", "dump", "badging", apk_path],
        ["apkanalyzer", "manifest", "application-id", apk_path],
    ):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
            )
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            match = re.search(r"package:\s+name='([^']+)'", output)
            if not match and cmd[0] == "apkanalyzer":
                plain = (result.stdout or "").strip()
                if plain and "." in plain:
                    package = plain
                else:
                    package = None
            elif match:
                package = match.group(1).strip()
            else:
                package = None

            if package:
                logger.info("Detected package name via %s: %s", cmd[0], package)
                return package
        except FileNotFoundError:
            logger.debug("Package detection tool not available: %s", cmd[0])
        except Exception as exc:
            logger.debug("Package detection via %s failed: %s", cmd[0], exc)
    return None


def _preflight_emulator_proxy_before_install(
    host: str,
    port: int,
    android_runner: AndroidRunner,
) -> Dict[str, Any]:
    """Ensure emulator proxy state is clean before a new APK install begins."""
    return android_proxy_runtime.preflight_android_proxy_before_install(
        emulator_host=host,
        emulator_port=port,
        runner=android_runner,
    )


def run_dynamic_analysis(task_id: str) -> dict:
    """Dynamic stage entrypoint."""
    from modules.task_orchestration.stage_services import run_dynamic_stage

    return run_dynamic_stage(task_id=task_id, retry_context=None)


def _build_dynamic_backend(backend_name: str):
    """Construct the configured dynamic analysis backend adapter."""
    if backend_name == "redroid_remote":
        from modules.analysis_backends.redroid_remote import RedroidRemoteDynamicBackend

        return RedroidRemoteDynamicBackend()
    raise ValueError(f"Unsupported ANALYSIS_BACKEND: {backend_name}")


def _run_dynamic_stage_impl(
    task_id: str,
    retry_context: Optional[object] = None,
) -> dict:
    """Dynamic stage dispatcher."""
    backend = _build_dynamic_backend(settings.ANALYSIS_BACKEND)
    return backend.run(task_id, retry_context=retry_context)

