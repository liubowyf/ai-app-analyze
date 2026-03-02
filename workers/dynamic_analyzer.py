"""Dynamic analysis stage service."""
import argparse
import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
import os
import time
import uuid

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
from modules.emulator_pool import EmulatorLeaseManager
from modules.traffic_monitor import TrafficMonitor
from modules.traffic_monitor.proxy_port_lease import ProxyPortLeaseManager
from modules.ai_driver import AIDriver
from modules.screenshot_manager.manager import ScreenshotManager
from modules.exploration_strategy.explorer import AppExplorer
from modules.exploration_strategy.policy import ExplorationPolicy
from modules.domain_analyzer.analyzer import MasterDomainAnalyzer
from modules.task_orchestration.run_tracker import (
    finish_stage_run,
    start_stage_run,
    update_stage_context,
)

logger = logging.getLogger(__name__)

MAX_DB_PAYLOAD_BYTES = 3_500_000  # keep below typical 4MB MySQL packet limit
MAX_DB_SCREENSHOTS = 25
MAX_DB_REQUESTS = 1000


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


EMULATOR_LEASE_MANAGER = EmulatorLeaseManager(
    lease_ttl_seconds=settings.emulator_lease_ttl_seconds,
)
PROXY_PORT_LEASE_MANAGER = ProxyPortLeaseManager(
    port_start=settings.TRAFFIC_PROXY_PORT_START,
    port_end=settings.TRAFFIC_PROXY_PORT_END,
    lease_ttl_seconds=settings.traffic_proxy_lease_ttl_seconds,
)
EMULATOR_WAIT_RETRY_SECONDS = max(5, int(os.getenv("EMULATOR_WAIT_RETRY_SECONDS", "20")))
EMULATOR_WAIT_MAX_RETRIES = max(1, int(os.getenv("EMULATOR_WAIT_MAX_RETRIES", "45")))
PROXY_PORT_WAIT_RETRY_SECONDS = max(5, int(os.getenv("PROXY_PORT_WAIT_RETRY_SECONDS", "12")))
PROXY_PORT_WAIT_MAX_RETRIES = max(1, int(os.getenv("PROXY_PORT_WAIT_MAX_RETRIES", "90")))

def get_available_emulator(task_id: str) -> Optional[Dict]:
    """
    Get an available emulator via distributed lease.

    Returns:
        Emulator config dict or None if all are busy
    """
    leased = EMULATOR_LEASE_MANAGER.acquire(task_id=task_id)
    if leased:
        logger.info(
            "Allocated emulator via lease %s:%s task=%s backend=%s",
            leased["host"],
            leased["port"],
            task_id,
            leased.get("lease_backend", "mysql"),
        )
        return leased
    logger.warning("No available emulator lease for task=%s", task_id)
    return None


def release_emulator(emulator: Dict) -> None:
    """
    Release an emulator distributed lease.

    Args:
        emulator: Emulator config dict
    """
    if not emulator:
        return

    if emulator.get("host") is not None and emulator.get("port") is not None:
        released = EMULATOR_LEASE_MANAGER.release(emulator)
        if released:
            logger.info(
                "Released emulator lease %s:%s",
                emulator.get("host"),
                emulator.get("port"),
            )
            return

    logger.warning(
        "Failed to release emulator lease cleanly %s:%s token=%s",
        emulator.get("host"),
        emulator.get("port"),
        str(emulator.get("lease_token") or "")[:8] or "-",
    )


def get_available_proxy_port(task_id: str) -> Optional[Dict]:
    """
    Get an available proxy port via distributed lease.

    Returns:
        Proxy lease dict or None if all ports are busy
    """
    leased = PROXY_PORT_LEASE_MANAGER.acquire(task_id=task_id)
    if leased:
        logger.info(
            "Allocated proxy port via lease node=%s port=%s task=%s backend=%s",
            leased.get("node_name"),
            leased.get("port"),
            task_id,
            leased.get("lease_backend", "mysql"),
        )
        return leased
    logger.warning("No available proxy port lease for task=%s", task_id)
    return None


def release_proxy_port(proxy_lease: Optional[Dict]) -> None:
    """Release a leased proxy port."""
    if not proxy_lease:
        return
    released = PROXY_PORT_LEASE_MANAGER.release(proxy_lease)
    if released:
        logger.info(
            "Released proxy port lease node=%s port=%s",
            proxy_lease.get("node_name"),
            proxy_lease.get("port"),
        )
        return
    logger.warning(
        "Failed to release proxy port lease node=%s port=%s token=%s",
        proxy_lease.get("node_name"),
        proxy_lease.get("port"),
        str(proxy_lease.get("lease_token") or "")[:8] or "-",
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
    return {
        "exploration_result": {
            "total_steps": exploration_result.total_steps,
            "screenshots": _compact_screenshots(exploration_result.screenshots, max_screenshots),
            "activities_visited": exploration_result.activities_visited,
            "success": exploration_result.success,
            "error_message": exploration_result.error_message,
            "phases_completed": exploration_result.phases_completed,
            "history": exploration_result.history[-300:],
        },
        "network_analysis": traffic_monitor.analyze_traffic(),
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


def _persist_dynamic_normalized_tables(
    db: Session,
    task_id: str,
    package_name: Optional[str],
    exploration_result: Any,
    traffic_monitor: TrafficMonitor,
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

        # Ensure idempotency for retries.
        db.query(NetworkRequestTable).filter(NetworkRequestTable.task_id == task_id).delete(synchronize_session=False)
        db.query(MasterDomainTable).filter(MasterDomainTable.task_id == task_id).delete(synchronize_session=False)
        db.query(ScreenshotTable).filter(ScreenshotTable.task_id == task_id).delete(synchronize_session=False)
        db.query(DynamicAnalysisTable).filter(DynamicAnalysisTable.task_id == task_id).delete(synchronize_session=False)

        unique_domains = {
            (item.get("host") or "").strip().lower()
            for item in all_requests
            if item.get("host")
        }
        dynamic_row = DynamicAnalysisTable(
            task_id=task_id,
            total_steps=int(getattr(exploration_result, "total_steps", 0) or 0),
            phases_completed=",".join(getattr(exploration_result, "phases_completed", []) or []),
            unique_activities=len(set(getattr(exploration_result, "activities_visited", []) or [])),
            activities_list=json.dumps(getattr(exploration_result, "activities_visited", []) or [], ensure_ascii=False),
            total_screenshots=len(getattr(exploration_result, "screenshots", []) or []),
            total_requests=len(all_requests),
            unique_domains=len(unique_domains),
            master_domains=len((domain_report or {}).get("master_domains", []) or []),
            success=1 if getattr(exploration_result, "success", False) else 0,
            error_message=getattr(exploration_result, "error_message", None),
            detected_package=package_name,
            started_at=None,
            completed_at=datetime.utcnow(),
            duration_seconds=0,
        )
        db.add(dynamic_row)

        for item in primary_requests[:3000]:
            db.add(
                NetworkRequestTable(
                    task_id=task_id,
                    url=item.get("url"),
                    method=item.get("method"),
                    host=item.get("host"),
                    path=item.get("path"),
                    ip=item.get("ip"),
                    port=int(item.get("port") or 80),
                    scheme=item.get("scheme"),
                    response_code=item.get("response_code"),
                    content_type=item.get("content_type"),
                    request_size=0,
                    response_size=0,
                    request_time=_safe_parse_datetime(item.get("request_time")),
                    has_sensitive_data=0,
                    sensitive_types=None,
                )
            )

        for row in (domain_report or {}).get("master_domains", []) or []:
            evidence = row.get("evidence")
            evidence_text = json.dumps(evidence, ensure_ascii=False) if evidence is not None else None
            db.add(
                MasterDomainTable(
                    task_id=task_id,
                    domain=row.get("domain"),
                    ip=row.get("ip"),
                    confidence_score=int(row.get("score", 0) or 0),
                    confidence_level=row.get("confidence"),
                    evidence=evidence_text,
                    request_count=int(row.get("request_count", 0) or 0),
                    post_count=int(row.get("post_count", 0) or 0),
                )
            )

        for shot in (getattr(exploration_result, "screenshots", []) or [])[:300]:
            storage_path = shot.get("storage_path")
            stage = shot.get("stage")
            description = shot.get("description")
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


def _parse_emulator_address(value: str) -> Optional[Dict[str, Any]]:
    """Parse emulator address string host:port."""
    if not value or ":" not in value:
        return None
    host, port_raw = value.rsplit(":", 1)
    try:
        port = int(port_raw)
    except ValueError:
        return None
    return {"host": host.strip(), "port": port}


def _minimal_emulator_candidates() -> list[Dict[str, Any]]:
    """Build minimal-mode emulator candidates in preferred order."""
    preferred = [
        settings.ANDROID_EMULATOR_4,
        settings.ANDROID_EMULATOR_2,
        settings.ANDROID_EMULATOR_3,
    ]
    candidates: list[Dict[str, Any]] = []
    seen = set()
    for item in preferred:
        parsed = _parse_emulator_address(item)
        if not parsed:
            continue
        key = f"{parsed['host']}:{parsed['port']}"
        if key in seen:
            continue
        seen.add(key)
        candidates.append(parsed)
    return candidates


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


def _write_minimal_markdown_report(
    output_path: Path,
    apk_path: str,
    package_name: Optional[str],
    emulator: Dict[str, Any],
    exploration_result,
    traffic_monitor: TrafficMonitor,
    domain_report: Dict[str, Any],
) -> None:
    """Write a local markdown report for minimal-mode run."""
    primary_requests = traffic_monitor.get_requests_as_dict()
    candidate_requests = getattr(traffic_monitor, "get_candidate_requests_as_dict", lambda: [])()
    aggregated_primary = traffic_monitor.get_aggregated_requests()
    aggregated_candidate = getattr(traffic_monitor, "get_candidate_aggregated_requests", lambda: [])()
    network_analysis = traffic_monitor.analyze_traffic()
    capture_diagnostics = getattr(traffic_monitor, "get_capture_diagnostics", lambda: {})()
    cert_diag = capture_diagnostics.get("cert", {}) if isinstance(capture_diagnostics, dict) else {}
    tls_diag = capture_diagnostics.get("tls", {}) if isinstance(capture_diagnostics, dict) else {}
    cert_status = cert_diag.get("verification_status", "unknown")
    tls_fail_total = int(tls_diag.get("total_failures", 0) or 0)
    tls_fail_by_host = tls_diag.get("by_host", {}) if isinstance(tls_diag.get("by_host", {}), dict) else {}
    screenshots = exploration_result.screenshots or []
    history = getattr(exploration_result, "history", []) or []

    # Acceptance targets for this phase
    target_requests = 80
    target_screenshots = 10
    target_domains = 3
    combined_requests = primary_requests + candidate_requests
    combined_domains = sorted({item.get("host", "") for item in combined_requests if item.get("host")})

    # Build dynamic domain summary from both pools.
    domain_rows: Dict[str, Dict[str, Any]] = {}
    for pool_name, rows in (("主池(强归因)", primary_requests), ("候选池(低置信)", candidate_requests)):
        for item in rows:
            host = (item.get("host") or "").strip()
            if not host:
                continue
            row = domain_rows.setdefault(
                host,
                {
                    "host": host,
                    "count": 0,
                    "ips": set(),
                    "sources": set(),
                    "packages": set(),
                    "pools": set(),
                },
            )
            row["count"] += 1
            if item.get("ip"):
                row["ips"].add(item["ip"])
            if item.get("source"):
                row["sources"].add(item["source"])
            if item.get("package_name"):
                row["packages"].add(item["package_name"])
            row["pools"].add(pool_name)

    ranked_domains = sorted(domain_rows.values(), key=lambda x: x["count"], reverse=True)

    lines = [
        "# 动态分析线索报告（最简增强版）",
        "",
        "## 一、任务信息",
        "",
        f"- 生成时间: `{datetime.now().isoformat()}`",
        f"- APK 路径: `{apk_path}`",
        f"- 包名: `{package_name or 'unknown'}`",
        f"- 模拟器: `{emulator['host']}:{emulator['port']}`",
        f"- AI 模型: `{settings.AI_MODEL_NAME}` ({settings.AI_BASE_URL})",
        "",
        "## 二、覆盖率与达标情况",
        "",
        f"- 探索成功: `{exploration_result.success}`",
        f"- 总步骤: `{exploration_result.total_steps}`",
        f"- 活动页数量: `{len(exploration_result.activities_visited or [])}`",
        f"- 截图数量: `{len(screenshots)}` (目标 >= {target_screenshots})",
        f"- 主池请求数(强归因): `{len(primary_requests)}`",
        f"- 候选请求数(低置信): `{len(candidate_requests)}`",
        f"- 合并请求数: `{len(combined_requests)}` (目标 >= {target_requests})",
        f"- 动态域名数(合并): `{len(combined_domains)}` (目标 >= {target_domains})",
        f"- 请求数达标: `{'PASS' if len(combined_requests) >= target_requests else 'FAIL'}`",
        f"- 截图数达标: `{'PASS' if len(screenshots) >= target_screenshots else 'FAIL'}`",
        f"- 域名数达标: `{'PASS' if len(combined_domains) >= target_domains else 'FAIL'}`",
        f"- MITM 证书状态: `{cert_status}`",
        f"- TLS 握手失败总数: `{tls_fail_total}`",
        "",
        "## 三、页面操作时间线（前 120 步）",
        "",
        "| Step | Phase | Operation | Description |",
        "| ---: | --- | --- | --- |",
    ]

    if history:
        for item in history[:120]:
            lines.append(
                f"| {item.get('step', '')} | {item.get('phase', '')} | {item.get('operation', item.get('action', ''))} | {item.get('description', '')} |"
            )
    else:
        lines.append("| - | - | - | 无操作历史 |")

    lines.extend(
        [
            "",
            "## 四、动态访问域名信息（主池+候选池）",
            "",
            "| 域名 | 请求数 | IP | 来源 | 包名 | 池 |",
            "| --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in ranked_domains[:80]:
        lines.append(
            f"| {row['host']} | {row['count']} | {', '.join(sorted(row['ips'])) or '-'} | "
            f"{', '.join(sorted(row['sources'])) or '-'} | {', '.join(sorted(row['packages'])) or '-'} | "
            f"{', '.join(sorted(row['pools']))} |"
        )

    lines.extend(
        [
            "",
            "## 五、网络请求聚合",
            "",
            "### 5.1 主池（强归因）",
            "",
            "| Host | Path | Method | Count | Sources | Packages |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in aggregated_primary[:40]:
        lines.append(
            f"| {row.get('host','')} | {row.get('path','')} | {row.get('method','')} | {row.get('count',0)} | "
            f"{', '.join(row.get('sources', [])) or '-'} | {', '.join(row.get('packages', [])) or '-'} |"
        )

    lines.extend(
        [
            "",
            "### 5.2 候选池（低置信）",
            "",
            "| Host | Path | Method | Count | Sources | Packages |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in aggregated_candidate[:40]:
        lines.append(
            f"| {row.get('host','')} | {row.get('path','')} | {row.get('method','')} | {row.get('count',0)} | "
            f"{', '.join(row.get('sources', [])) or '-'} | {', '.join(row.get('packages', [])) or '-'} |"
        )

    lines.extend(
        [
            "",
            "## 六、HTTPS 拦截诊断",
            "",
            f"- 证书验证状态: `{cert_status}`",
            f"- 本地 CA 文件: `{cert_diag.get('local_cert_path', '-')}`",
            f"- 本地 CA 存在: `{cert_diag.get('local_cert_exists', False)}`",
            f"- 设备证书仓可访问: `{cert_diag.get('device_cert_store_accessible', 'unknown')}`",
            f"- 设备证书已安装(哈希校验): `{cert_diag.get('device_cert_installed', 'unknown')}`",
            f"- 设备证书检查路径: `{cert_diag.get('device_cert_checked_path', '-')}`",
            f"- 设备下载目录存在证书文件: `{cert_diag.get('device_download_cert_present', 'unknown')}`",
            f"- TLS 握手失败总数: `{tls_fail_total}`",
            "",
            "| Host | TLS 握手失败次数 |",
            "| --- | ---: |",
        ]
    )
    if tls_fail_by_host:
        for host, count in sorted(tls_fail_by_host.items(), key=lambda item: item[1], reverse=True)[:50]:
            lines.append(f"| {host} | {count} |")
    else:
        lines.append("| - | 0 |")

    lines.extend(
        [
            "",
            "## 七、DNS/IP 线索（运行时观测）",
            "",
            "| Domain | IP 列表 |",
            "| --- | --- |",
        ]
    )
    for row in ranked_domains[:50]:
        lines.append(f"| {row['host']} | {', '.join(sorted(row['ips'])) or '-'} |")

    lines.extend(["", "## 八、主控域名识别", ""])
    masters = domain_report.get("master_domains", []) if isinstance(domain_report, dict) else []
    if masters:
        lines.append("| Domain | Score | Confidence |")
        lines.append("| --- | ---: | --- |")
        for row in masters:
            lines.append(
                f"| {row.get('domain','')} | {row.get('score', 0)} | {row.get('confidence', '')} |"
            )
    else:
        lines.append("- 未识别到主控域名")

    lines.extend(
        [
            "",
            "## 九、请求样本（前 30 条主池 + 前 30 条候选池）",
            "",
            "### 9.1 主池请求样本",
            "",
            "| Method | URL | Source | Package | Confidence |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for item in primary_requests[:30]:
        lines.append(
            f"| {item.get('method','')} | {item.get('url','')} | {item.get('source','')} | "
            f"{item.get('package_name','')} | {item.get('attribution_confidence', 0)} |"
        )
    lines.extend(
        [
            "",
            "### 9.2 候选池请求样本",
            "",
            "| Method | URL | Source | Package | Confidence |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for item in candidate_requests[:30]:
        lines.append(
            f"| {item.get('method','')} | {item.get('url','')} | {item.get('source','')} | "
            f"{item.get('package_name','')} | {item.get('attribution_confidence', 0)} |"
        )

    lines.extend(["", "## 十、运行时截图索引", ""])
    if screenshots:
        for shot in screenshots:
            path = shot.get("storage_path")
            desc = shot.get("description", "")
            if path:
                try:
                    rel_path = os.path.relpath(path, output_path.parent)
                except Exception:
                    rel_path = path
                lines.append(f"- `{shot.get('stage', '')}` {desc} -> ![]({rel_path})")
            else:
                lines.append(f"- `{shot.get('stage', '')}` {desc}")
    else:
        lines.append("- 无截图")

    lines.extend(
        [
            "",
            "## 十一、补充统计",
            "",
            f"- 主池 unique hosts: `{network_analysis.get('unique_hosts', 0)}`",
            f"- 主池 source 分布: `{network_analysis.get('sources', {})}`",
            f"- 候选池 unique hosts: `{network_analysis.get('candidate_unique_hosts', 0)}`",
            f"- 候选池 source 分布: `{network_analysis.get('candidate_sources', {})}`",
            f"- TLS 握手失败域名分布: `{network_analysis.get('tls_handshake_failures_by_host', {})}`",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_dynamic_analysis_minimal(
    apk_path: str,
    output_dir: Optional[str] = None,
    max_steps: Optional[int] = None,
    emulator: Optional[str] = None,
) -> dict:
    """
    Run minimal dynamic analysis without DB/MinIO persistence.

    Core flow only: install APK -> AI exploration -> network monitoring.
    Results are written locally as screenshots + markdown report.
    """
    apk = Path(apk_path).expanduser().resolve()
    if not apk.exists():
        raise FileNotFoundError(f"APK file not found: {apk}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    base_dir = Path(output_dir).expanduser().resolve() if output_dir else Path("artifacts/minimal_runs") / run_id
    screenshot_dir = base_dir / "screenshots"
    report_path = base_dir / "report.md"
    base_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    android_runner = AndroidRunner()
    candidates = []
    if emulator:
        parsed = _parse_emulator_address(emulator)
        if not parsed:
            raise ValueError(f"Invalid emulator address: {emulator}")
        candidates.append(parsed)
    candidates.extend(_minimal_emulator_candidates())

    selected = None
    for item in candidates:
        if android_runner.connect_remote_emulator(item["host"], item["port"]):
            selected = item
            break
    if not selected:
        raise RuntimeError("No reachable emulator found for minimal analysis")

    package_name = _detect_package_name(str(apk))
    if package_name:
        logger.info("Detected package name for minimal run: %s", package_name)
    else:
        logger.warning("Package name detection failed in minimal mode; installer fallback will be used")

    proxy_lease = get_available_proxy_port(task_id=run_id)
    if not proxy_lease:
        raise RuntimeError("No available proxy ports for minimal analysis")

    screenshot_manager = ScreenshotManager(task_id=run_id)
    traffic_monitor = TrafficMonitor(proxy_port=int(proxy_lease["port"]))
    traffic_monitor.set_whitelist([])
    traffic_monitor.set_filter_policy(
        {
            "strict_target_package": bool(package_name),
            "candidate_limit": int(os.getenv("TRAFFIC_CANDIDATE_LIMIT", "5000")),
        }
    )

    ai_driver = AIDriver(
        base_url=settings.AI_BASE_URL,
        model_name=settings.AI_MODEL_NAME,
        api_key=settings.AI_API_KEY,
    )
    policy = ExplorationPolicy.from_env()
    if max_steps is not None:
        policy.max_steps = max(1, min(int(max_steps), 500))
    else:
        # Default to a higher exploration cap for richer dynamic evidence output.
        policy.max_steps = max(policy.max_steps, 140)
    policy.time_budget_seconds = min(policy.time_budget_seconds, 540)  # target 10-minute run

    explorer = AppExplorer(
        ai_driver=ai_driver,
        android_runner=android_runner,
        screenshot_manager=screenshot_manager,
        policy=policy,
    )

    old_env_steps = os.getenv("APP_EXPLORATION_MAX_STEPS")
    if max_steps is not None:
        os.environ["APP_EXPLORATION_MAX_STEPS"] = str(policy.max_steps)

    try:
        traffic_monitor.start(
            emulator_host=selected["host"],
            emulator_port=selected["port"],
            target_package=package_name,
            android_runner=android_runner,
            port_fallback_attempts=1,
        )

        exploration_result = explorer.run_full_exploration(
            emulator_config=selected,
            apk_info={"apk_path": str(apk), "package_name": package_name},
            persist_screenshots="local",
            local_screenshot_dir=str(screenshot_dir),
        )
    finally:
        traffic_monitor.stop()
        release_proxy_port(proxy_lease)
        if max_steps is not None:
            if old_env_steps is None:
                os.environ.pop("APP_EXPLORATION_MAX_STEPS", None)
            else:
                os.environ["APP_EXPLORATION_MAX_STEPS"] = old_env_steps

    network_requests = traffic_monitor.get_requests()
    candidate_requests = getattr(traffic_monitor, "get_candidate_requests", lambda: [])()
    domain_analyzer = MasterDomainAnalyzer()
    master_domains = domain_analyzer.analyze(network_requests)
    domain_report = domain_analyzer.generate_domain_report(master_domains)

    _write_minimal_markdown_report(
        output_path=report_path,
        apk_path=str(apk),
        package_name=package_name,
        emulator=selected,
        exploration_result=exploration_result,
        traffic_monitor=traffic_monitor,
        domain_report=domain_report,
    )

    combined_requests_count = len(network_requests) + len(candidate_requests)
    combined_domains_count = len(
        {
            req.host
            for req in list(network_requests) + list(candidate_requests)
            if getattr(req, "host", None)
        }
    )
    if not exploration_result.success:
        minimal_status = "failed_exploration"
        status_reason = "exploration_failed"
    elif combined_requests_count <= 0:
        minimal_status = "degraded_no_network"
        status_reason = "no_network_requests_captured"
    else:
        minimal_status = "success"
        status_reason = "ok"
    capture_diagnostics = getattr(traffic_monitor, "get_capture_diagnostics", lambda: {})()
    cert_diag = capture_diagnostics.get("cert", {}) if isinstance(capture_diagnostics, dict) else {}
    tls_diag = capture_diagnostics.get("tls", {}) if isinstance(capture_diagnostics, dict) else {}

    return {
        "status": minimal_status,
        "status_reason": status_reason,
        "mode": "minimal",
        "apk_path": str(apk),
        "package_name": package_name,
        "emulator": f"{selected['host']}:{selected['port']}",
        "proxy_port": int(proxy_lease["port"]),
        "output_dir": str(base_dir),
        "screenshots_dir": str(screenshot_dir),
        "report_path": str(report_path),
        "exploration_success": exploration_result.success,
        "exploration_steps": exploration_result.total_steps,
        "network_requests": len(network_requests),
        "candidate_requests": len(candidate_requests),
        "combined_requests": combined_requests_count,
        "combined_domains": combined_domains_count,
        "aggregated_requests": len(traffic_monitor.get_aggregated_requests()),
        "candidate_aggregated_requests": len(
            getattr(traffic_monitor, "get_candidate_aggregated_requests", lambda: [])()
        ),
        "cert_verification_status": cert_diag.get("verification_status", "unknown"),
        "tls_handshake_failures": int(tls_diag.get("total_failures", 0) or 0),
        "tls_handshake_failures_by_host": tls_diag.get("by_host", {}),
    }


def run_dynamic_analysis(task_id: str) -> dict:
    """Dynamic stage entrypoint."""
    from modules.task_orchestration.stage_services import run_dynamic_stage

    return run_dynamic_stage(task_id=task_id, retry_context=None)


def _run_dynamic_stage_impl(
    task_id: str,
    retry_context: Optional[object] = None,
) -> dict:
    """
    Run dynamic analysis on an APK file.

    Args:
        task_id: Task ID to process

    Returns:
        Analysis result dict
    """
    db: Session = SessionLocal()
    task: Optional[Task] = None
    emulator: Optional[Dict] = None
    proxy_lease: Optional[Dict] = None
    traffic_monitor: Optional[TrafficMonitor] = None
    apk_temp_path: Optional[str] = None

    try:
        task_context = retry_context
        # 1. Get Task
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        task.status = TaskStatus.DYNAMIC_ANALYZING
        start_stage_run(db, task_id=task_id, stage="dynamic")
        _commit_with_retry(db, context="set_dynamic_analyzing")

        logger.info(f"Starting dynamic analysis for task {task_id}")

        # Get whitelist from database
        from models.whitelist import WhitelistRule
        whitelist_rules = db.query(WhitelistRule).filter(
            WhitelistRule.is_active == True
        ).all()
        whitelist_domains = [rule.domain for rule in whitelist_rules]

        # 2. Select available emulator
        emulator = get_available_emulator(task_id=task_id)
        if not emulator:
            retry_attempt = getattr(getattr(task_context, "request", None), "retries", 0) + 1
            logger.info(
                "No emulator slot for task=%s, retry in %ss (attempt %s/%s)",
                task_id,
                EMULATOR_WAIT_RETRY_SECONDS,
                retry_attempt,
                EMULATOR_WAIT_MAX_RETRIES,
            )
            if task_context is not None and hasattr(task_context, "retry"):
                raise task_context.retry(
                    countdown=EMULATOR_WAIT_RETRY_SECONDS,
                    max_retries=EMULATOR_WAIT_MAX_RETRIES,
                    exc=RuntimeError("No available emulators in distributed lease pool"),
                )
            raise RuntimeError("No available emulators in distributed lease pool")

        proxy_lease = get_available_proxy_port(task_id=task_id)
        if not proxy_lease:
            retry_attempt = getattr(getattr(task_context, "request", None), "retries", 0) + 1
            logger.info(
                "No proxy port slot for task=%s, retry in %ss (attempt %s/%s)",
                task_id,
                PROXY_PORT_WAIT_RETRY_SECONDS,
                retry_attempt,
                PROXY_PORT_WAIT_MAX_RETRIES,
            )
            if task_context is not None and hasattr(task_context, "retry"):
                raise task_context.retry(
                    countdown=PROXY_PORT_WAIT_RETRY_SECONDS,
                    max_retries=PROXY_PORT_WAIT_MAX_RETRIES,
                    exc=RuntimeError("No available proxy ports in distributed lease pool"),
                )
            raise RuntimeError("No available proxy ports in distributed lease pool")
        proxy_port = int(proxy_lease["port"])

        host = emulator["host"]
        port = emulator["port"]
        update_stage_context(
            db,
            task_id=task_id,
            stage="dynamic",
            emulator=f"{host}:{port}",
        )

        # 3. Connect to emulator
        android_runner = AndroidRunner()
        if not android_runner.connect_remote_emulator(host, port):
            raise RuntimeError(f"Failed to connect to emulator {host}:{port}")

        logger.info(f"Connected to emulator {host}:{port}")

        # Download APK from MinIO
        apk_content = storage_client.download_file(task.apk_storage_path)

        # Save APK to temporary file
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tmp:
            tmp.write(apk_content)
            apk_temp_path = tmp.name

        logger.info(f"APK downloaded to {apk_temp_path}")

        # Get package name from static analysis result or extract from APK
        package_name = None
        if task.static_analysis_result:
            package_name = task.static_analysis_result.get("package_name")

        # If no package name from static analysis, try to extract it from APK
        if not package_name:
            logger.info("Extracting package name from APK (no static analysis result)")
            package_name = _detect_package_name(apk_temp_path)
            if package_name:
                logger.info(f"Package name extracted: {package_name}")
            else:
                logger.warning("Failed to extract package name from APK")

        # package_name可以为None,后续install_apk_remote会处理
        if package_name:
            logger.info(f"Using package name: {package_name}")
        else:
            logger.warning("No package name available, proceeding with dynamic analysis anyway")

        # 4. Create ScreenshotManager instance
        screenshot_manager = ScreenshotManager(task_id=task_id)

        # Initialize components
        traffic_monitor = TrafficMonitor(proxy_port=proxy_port)
        traffic_monitor.set_whitelist(whitelist_domains)
        traffic_monitor.set_filter_policy(
            {
                "strict_target_package": os.getenv("TRAFFIC_STRICT_TARGET_PACKAGE", "true").strip().lower() in ("1", "true", "yes"),
                "include_packages": [
                    item.strip()
                    for item in os.getenv("TRAFFIC_INCLUDE_PACKAGES", "").split(",")
                    if item.strip()
                ],
                "include_uids": [
                    int(item.strip())
                    for item in os.getenv("TRAFFIC_INCLUDE_UIDS", "").split(",")
                    if item.strip().isdigit()
                ],
                "exclude_domains": [
                    item.strip()
                    for item in os.getenv("TRAFFIC_EXCLUDE_DOMAINS", "").split(",")
                    if item.strip()
                ],
                "exclude_process_prefixes": [
                    item.strip()
                    for item in os.getenv("TRAFFIC_EXCLUDE_PROCESS_PREFIXES", "").split(",")
                    if item.strip()
                ],
            }
        )

        ai_driver = AIDriver(
            base_url=settings.AI_BASE_URL,
            model_name=settings.AI_MODEL_NAME,
            api_key=settings.AI_API_KEY,
        )

        # 5. Create AppExplorer instance
        exploration_policy = ExplorationPolicy.from_env()
        app_explorer = AppExplorer(
            ai_driver=ai_driver,
            android_runner=android_runner,
            screenshot_manager=screenshot_manager,
            policy=exploration_policy,
        )

        # Start traffic monitoring with emulator info
        traffic_monitor.start(
            emulator_host=host,
            emulator_port=port,
            target_package=package_name,
            android_runner=android_runner,
            port_fallback_attempts=1,
        )

        # 6. Execute full exploration
        emulator_config = {"host": host, "port": port}
        apk_info = {
            "apk_path": apk_temp_path,
            "package_name": package_name
        }

        exploration_result = app_explorer.run_full_exploration(
            emulator_config=emulator_config,
            apk_info=apk_info
        )

        logger.info(f"Exploration completed: {exploration_result.total_steps} steps, "
                   f"{len(exploration_result.screenshots)} screenshots")

        # 7. Analyze network requests
        traffic_monitor.stop()

        # Collect network requests
        network_requests = traffic_monitor.get_requests()
        candidate_requests = getattr(traffic_monitor, "get_candidate_requests", lambda: [])()

        # Use MasterDomainAnalyzer to identify master control domains
        domain_analyzer = MasterDomainAnalyzer()
        master_domains = domain_analyzer.analyze(network_requests)

        logger.info(f"Identified {len(master_domains)} master control domains")

        # Generate domain analysis report
        domain_report = domain_analyzer.generate_domain_report(master_domains)

        # 8. Store results
        dynamic_result = _build_dynamic_result(
            exploration_result=exploration_result,
            traffic_monitor=traffic_monitor,
            domain_report=domain_report,
            max_screenshots=MAX_DB_SCREENSHOTS,
            max_requests=MAX_DB_REQUESTS,
        )
        quality_gate = _build_dynamic_quality_gate(
            screenshot_count=len(exploration_result.screenshots or []),
            primary_request_count=len(network_requests or []),
            candidate_request_count=len(candidate_requests or []),
            master_domain_count=len(master_domains or []),
        )
        dynamic_result["quality_gate"] = quality_gate
        if quality_gate["degraded"]:
            logger.warning(
                "Dynamic evidence degraded task=%s reason=%s",
                task_id,
                quality_gate["reason"],
            )

        payload_size = len(json.dumps(dynamic_result, ensure_ascii=False))
        if payload_size > MAX_DB_PAYLOAD_BYTES:
            logger.warning(
                "Dynamic result payload too large (%s bytes), reducing screenshots/requests",
                payload_size,
            )
            dynamic_result = _build_dynamic_result(
                exploration_result=exploration_result,
                traffic_monitor=traffic_monitor,
                domain_report=domain_report,
                max_screenshots=10,
                max_requests=300,
            )
            payload_size = len(json.dumps(dynamic_result, ensure_ascii=False))
            logger.info("Reduced dynamic result payload size: %s bytes", payload_size)
            dynamic_result["quality_gate"] = quality_gate

        task.dynamic_analysis_result = dynamic_result
        task.error_message = (
            f"degraded:{quality_gate['reason']}"
            if quality_gate["degraded"]
            else None
        )
        _persist_dynamic_normalized_tables(
            db=db,
            task_id=task_id,
            package_name=package_name,
            exploration_result=exploration_result,
            traffic_monitor=traffic_monitor,
            domain_report=domain_report,
        )
        finish_stage_run(
            db,
            task_id=task_id,
            stage="dynamic",
            success=True,
            details={
                "steps": exploration_result.total_steps,
                "primary_requests": len(network_requests),
                "candidate_requests": len(candidate_requests),
                "master_domains": len(master_domains),
                "degraded": quality_gate["degraded"],
                "degraded_reason": quality_gate["reason"],
            },
        )
        _commit_with_retry(db, context="save_dynamic_result")

        logger.info(f"Dynamic analysis completed for task {task_id}")

        return {
            "task_id": task_id,
            "status": "success",
            "exploration_steps": exploration_result.total_steps,
            "screenshots": len(exploration_result.screenshots),
            "network_requests": len(network_requests),
            "candidate_requests": len(candidate_requests),
            "master_domains": len(master_domains),
            "quality_gate": quality_gate,
        }

    except Exception as e:
        # Keep compatibility with retry-style task contexts that raise Retry.
        if e.__class__.__name__ == "Retry":
            raise
        logger.error(f"Dynamic analysis failed for task {task_id}: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        _mark_task_failed(task_id, str(e))
        raise

    finally:
        if traffic_monitor and traffic_monitor.is_running:
            try:
                traffic_monitor.stop()
            except Exception as e:
                logger.error("Failed to stop traffic monitor in cleanup: %s", e)

        if proxy_lease:
            release_proxy_port(proxy_lease)

        # 9. Release emulator and cleanup
        if emulator:
            release_emulator(emulator)

        # Clean up temporary APK file
        if apk_temp_path and os.path.exists(apk_temp_path):
            try:
                os.unlink(apk_temp_path)
                logger.info(f"Cleaned up temporary APK file: {apk_temp_path}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary file: {e}")

        db.close()


def _build_cli_parser() -> argparse.ArgumentParser:
    """Build command-line parser for local minimal mode."""
    parser = argparse.ArgumentParser(description="Dynamic analyzer utility")
    parser.add_argument("--minimal", action="store_true", help="Run minimal local mode")
    parser.add_argument("--apk-path", help="Local APK path for minimal mode")
    parser.add_argument("--output-dir", help="Output directory for minimal artifacts")
    parser.add_argument("--max-steps", type=int, help="Max exploration steps in minimal mode")
    parser.add_argument("--emulator", help="Specific emulator host:port")
    return parser


if __name__ == "__main__":
    cli = _build_cli_parser()
    args = cli.parse_args()
    if not args.minimal:
        cli.error("Only --minimal mode is supported from CLI entrypoint")
    if not args.apk_path:
        cli.error("--apk-path is required in --minimal mode")
    result = run_dynamic_analysis_minimal(
        apk_path=args.apk_path,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        emulator=args.emulator,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
