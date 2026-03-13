"""Redroid remote dynamic analysis adapter."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.ai_driver import AIDriver
from modules.android_runner import AndroidRunner
from modules.domain_analyzer.analyzer import MasterDomainAnalyzer
from modules.exploration_strategy.explorer import AppExplorer
from modules.exploration_strategy.policy import ExplorationPolicy
from modules.redroid_remote.adb_client import RedroidADBClient
from modules.redroid_remote.device_controller import RedroidDeviceController
from modules.redroid_remote.host_agent_client import RedroidHostAgentClient
from modules.redroid_remote.lease_manager import RedroidLeaseManager
from modules.redroid_remote.result_assembler import (
    REDROID_CAPTURE_MODE,
    assemble_redroid_observation_adapter,
)
from modules.redroid_remote.traffic_collector import RedroidTrafficCollector
from modules.redroid_remote.traffic_parser import parse_zeek_outputs
from modules.screenshot_manager.manager import ScreenshotManager
from modules.task_orchestration.run_tracker import finish_stage_run, start_stage_run, update_stage_context

from .base import DynamicAnalysisBackend

logger = logging.getLogger(__name__)
_LAUNCHABLE_ACTIVITY_RE = re.compile(r"launchable-activity:\s+name='([^']+)'")
_MANIFEST_ACTIVITY_RE = re.compile(r'A: android:name\(0x01010003\)="([^"]+)"')


def _dynamic_helpers():
    """Lazy import to avoid dynamic_analyzer/backend circular import at module load."""
    from workers import dynamic_analyzer

    return dynamic_analyzer


def _fetch_optional_remote_file(
    host_agent_client: RedroidHostAgentClient,
    capture_id: str,
    name: str,
    local_path: str,
) -> str:
    """Fetch an optional capture artifact from the host agent."""
    try:
        return host_agent_client.download_capture_file(capture_id, name, local_path)
    except Exception:
        return ""


def _resolve_package_name(task: Task, apk_path: str) -> Optional[str]:
    """Resolve package name from static result or APK fallback."""
    helpers = _dynamic_helpers()
    package_name = None
    if task.static_analysis_result:
        package_name = helpers._get_static_package_name(task.static_analysis_result)
    if not package_name:
        package_name = helpers._detect_package_name(apk_path)
    return package_name


def _resolve_activity_name(task: Task, apk_path: str) -> Optional[str]:
    try:
        output = subprocess.check_output(
            ["aapt", "dump", "badging", apk_path],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("Failed to resolve launchable activity via aapt for %s: %s", apk_path, exc)
        output = ""

    match = _LAUNCHABLE_ACTIVITY_RE.search(output)
    if match:
        return match.group(1).strip()

    try:
        manifest_output = subprocess.check_output(
            ["aapt", "dump", "xmltree", apk_path, "AndroidManifest.xml"],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("Failed to resolve launcher activity via manifest xmltree for %s: %s", apk_path, exc)
        return None

    lines = manifest_output.splitlines()
    current_activity: Optional[str] = None
    current_block: list[str] = []

    def _match_launcher(block_activity: Optional[str], block_lines: list[str]) -> Optional[str]:
        if not block_activity:
            return None
        block_text = "\n".join(block_lines)
        if (
            "android.intent.action.MAIN" in block_text
            and "android.intent.category.LAUNCHER" in block_text
        ):
            return block_activity
        return None

    for line in lines:
        if "E: activity" in line:
            matched = _match_launcher(current_activity, current_block)
            if matched:
                return matched
            current_activity = None
            current_block = [line]
            continue
        if current_block:
            current_block.append(line)
            activity_match = _MANIFEST_ACTIVITY_RE.search(line)
            if activity_match and current_activity is None:
                current_activity = activity_match.group(1).strip()

    matched = _match_launcher(current_activity, current_block)
    if matched:
        return matched

    static_result = task.static_analysis_result if isinstance(task.static_analysis_result, dict) else {}
    components = static_result.get("components")
    if isinstance(components, list):
        preferred: list[str] = []
        fallback: list[str] = []
        for component in components:
            if not isinstance(component, dict):
                continue
            if component.get("component_type") != "activity":
                continue
            component_name = component.get("component_name")
            if not (isinstance(component_name, str) and component_name.strip()):
                continue
            intent_filters = component.get("intent_filters") or []
            if any("android.intent.action.MAIN" in str(item) for item in intent_filters):
                preferred.append(component_name.strip())
            else:
                fallback.append(component_name.strip())
        if preferred:
            return preferred[0]
        if fallback:
            return fallback[0]
    return None


def _resolve_redroid_host_port(serial: str) -> tuple[str, int]:
    if not serial or ":" not in serial:
        raise RuntimeError(f"Invalid REDROID_ADB_SERIAL: {serial!r}")
    host, port_raw = serial.rsplit(":", 1)
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid REDROID_ADB_SERIAL port: {serial!r}") from exc
    return host.strip(), port


class RedroidRemoteDynamicBackend(DynamicAnalysisBackend):
    """Dynamic backend that runs APKs on a remote redroid node and parses Zeek outputs."""

    backend_name = "redroid_remote"

    @staticmethod
    def _valid_screenshots(exploration_result: Any) -> list[dict[str, Any]]:
        screenshots = getattr(exploration_result, "screenshots", []) or []
        return [
            shot
            for shot in screenshots
            if isinstance(shot, dict) and (shot.get("storage_path") or shot.get("image_base64"))
        ]

    def run(self, task_id: str, retry_context: object | None = None) -> dict[str, Any]:
        helpers = _dynamic_helpers()
        db: Session = SessionLocal()
        task: Optional[Task] = None
        traffic_collector: Optional[RedroidTrafficCollector] = None
        capture: Optional[dict[str, Any]] = None
        apk_temp_path: Optional[str] = None
        local_artifact_dir: Optional[Path] = None
        slot_name: Optional[str] = None

        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise ValueError(f"Task {task_id} not found")

            if not settings.REDROID_HOST_AGENT_BASE_URL:
                raise RuntimeError("REDROID_HOST_AGENT_BASE_URL is required for ANALYSIS_BACKEND=redroid_remote")

            lease_manager = RedroidLeaseManager(
                settings.redroid_slots,
                ttl_seconds=settings.REDROID_LEASE_TTL_SECONDS,
                acquire_timeout_seconds=settings.REDROID_LEASE_ACQUIRE_TIMEOUT_SECONDS,
                poll_interval_seconds=settings.REDROID_LEASE_POLL_INTERVAL_SECONDS,
            )
            slot = lease_manager.acquire(task_id)
            slot_name = slot["name"]
            serial = slot["adb_serial"]
            container_name = slot["container_name"]
            host, port = _resolve_redroid_host_port(serial)

            task.status = TaskStatus.DYNAMIC_ANALYZING
            start_stage_run(
                db,
                task_id=task_id,
                stage="dynamic",
                details={
                    "capture_mode": REDROID_CAPTURE_MODE,
                    "lease_scope": "redroid_slot_lease",
                    "resource_wait": "redroid_slot",
                    "analysis_backend": self.backend_name,
                    "redroid_slot": slot_name,
                },
            )
            helpers._commit_with_retry(db, context="set_redroid_dynamic_analyzing")

            adb_client = RedroidADBClient(serial)
            if not adb_client.connect():
                raise RuntimeError(f"Failed to connect redroid ADB device {serial}")

            host_agent_client = RedroidHostAgentClient(
                settings.REDROID_HOST_AGENT_BASE_URL,
                token=settings.REDROID_HOST_AGENT_TOKEN or None,
                timeout=settings.REDROID_HOST_AGENT_TIMEOUT_SECONDS,
            )
            traffic_collector = RedroidTrafficCollector(
                host_agent_client=host_agent_client,
                slot_name=slot_name,
                container_name=container_name,
            )

            update_stage_context(
                db,
                task_id=task_id,
                stage="dynamic",
                emulator=serial,
                details={
                    "analysis_backend": self.backend_name,
                    "emulator_slot": serial,
                    "redroid_slot": slot_name,
                    "redroid_host_agent": settings.REDROID_HOST_AGENT_BASE_URL,
                    "redroid_container": container_name,
                },
            )

            apk_content = storage_client.download_file(task.apk_storage_path)
            if not apk_content:
                raise RuntimeError(f"Failed to download APK from storage: {task.apk_storage_path}")

            with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as tmp:
                tmp.write(apk_content)
                apk_temp_path = tmp.name

            package_name = _resolve_package_name(task, apk_temp_path)
            if not package_name:
                raise RuntimeError("Unable to determine package name for redroid remote analysis")
            activity_name = _resolve_activity_name(task, apk_temp_path)
            if activity_name:
                logger.info("Resolved redroid launch activity for %s: %s", package_name, activity_name)
            else:
                logger.warning("No explicit redroid launch activity resolved for %s; fallback to package launch", package_name)

            # Best-effort preflight against stale localhost proxies before install.
            helpers._preflight_emulator_proxy_before_install(
                host=host,
                port=port,
                android_runner=AndroidRunner(),
            )

            capture = traffic_collector.start_capture(task_id)
            local_artifact_dir = Path(tempfile.mkdtemp(prefix=f"redroid-{task_id[:8]}-"))

            screenshot_manager = ScreenshotManager(task_id=task_id)
            android_runner = AndroidRunner()
            ai_driver = AIDriver(
                base_url=settings.AI_BASE_URL,
                model_name=settings.AI_MODEL_NAME,
                api_key=settings.AI_API_KEY,
            )
            policy = ExplorationPolicy.from_env()
            explorer = AppExplorer(
                ai_driver=ai_driver,
                android_runner=android_runner,
                screenshot_manager=screenshot_manager,
                policy=policy,
            )

            exploration_result = explorer.run_full_exploration(
                emulator_config={"host": host, "port": port},
                apk_info={
                    "apk_path": apk_temp_path,
                    "package_name": package_name,
                    "activity_name": activity_name,
                },
            )
            if not getattr(exploration_result, "success", False):
                error_message = getattr(exploration_result, "error_message", None) or "redroid exploration failed"
                raise RuntimeError(error_message)

            valid_screenshots = self._valid_screenshots(exploration_result)
            if len(valid_screenshots) != len(getattr(exploration_result, "screenshots", []) or []):
                exploration_result = replace(exploration_result, screenshots=valid_screenshots)

            # Additional UI XML artifact for the remote backend.
            try:
                RedroidDeviceController(adb_client).dump_ui_xml(
                    str(local_artifact_dir),
                    file_name="window_dump.xml",
                )
            except Exception as exc:
                logger.warning("Failed to capture redroid UI XML artifact task=%s: %s", task_id, exc)

            traffic_collector.stop_capture(capture)
            zeek_result = traffic_collector.run_zeek(capture)
            capture_id = str(capture.get("capture_id") or "").strip()

            tcpdump_text_local = _fetch_optional_remote_file(
                host_agent_client,
                capture_id,
                "tcpdump.log",
                str(local_artifact_dir / "tcpdump.log"),
            )

            conn_local = _fetch_optional_remote_file(
                host_agent_client,
                capture_id,
                "conn.log",
                str(local_artifact_dir / "conn.log"),
            )
            dns_local = _fetch_optional_remote_file(
                host_agent_client,
                capture_id,
                "dns.log",
                str(local_artifact_dir / "dns.log"),
            )
            ssl_local = _fetch_optional_remote_file(
                host_agent_client,
                capture_id,
                "ssl.log",
                str(local_artifact_dir / "ssl.log"),
            )
            http_local = _fetch_optional_remote_file(
                host_agent_client,
                capture_id,
                "http.log",
                str(local_artifact_dir / "http.log"),
            )

            parsed = parse_zeek_outputs(
                conn_log=Path(conn_local).read_text(encoding="utf-8") if conn_local and Path(conn_local).exists() else "",
                dns_log=Path(dns_local).read_text(encoding="utf-8") if dns_local and Path(dns_local).exists() else "",
                ssl_log=Path(ssl_local).read_text(encoding="utf-8") if ssl_local and Path(ssl_local).exists() else "",
                http_log=Path(http_local).read_text(encoding="utf-8") if http_local and Path(http_local).exists() else "",
                tcpdump_log=Path(tcpdump_text_local).read_text(encoding="utf-8") if tcpdump_text_local and Path(tcpdump_text_local).exists() else "",
            )

            traffic_adapter, domain_report = assemble_redroid_observation_adapter(parsed)
            network_requests = traffic_adapter.get_requests()
            candidate_requests = traffic_adapter.get_candidate_requests()
            master_domains = domain_report.get("master_domains", [])

            dynamic_result = helpers._build_dynamic_result(
                exploration_result=exploration_result,
                traffic_monitor=traffic_adapter,
                domain_report=domain_report,
                max_screenshots=helpers.MAX_DB_SCREENSHOTS,
                max_requests=helpers.MAX_DB_REQUESTS,
            )
            dynamic_result["redroid_artifacts"] = {
                "capture_id": capture_id or None,
                "slot_name": slot_name,
                "host_agent_base_url": settings.REDROID_HOST_AGENT_BASE_URL,
                "pcap_path": zeek_result["pcap_path"],
                "zeek_dir": zeek_result["zeek_dir"],
                "pcap_exists": zeek_result.get("pcap_exists", False),
                "pcap_size": zeek_result.get("pcap_size", 0),
                "tcpdump_log_path": tcpdump_text_local or None,
                "ui_xml_path": str(local_artifact_dir / "window_dump.xml"),
                "conn_log_path": conn_local or None,
                "dns_log_path": dns_local or None,
                "ssl_log_path": ssl_local or None,
                "http_log_path": http_local or None,
            }
            quality_gate = helpers._build_dynamic_quality_gate(
                screenshot_count=len(exploration_result.screenshots or []),
                primary_request_count=len(network_requests or []),
                candidate_request_count=len(candidate_requests or []),
                master_domain_count=len(master_domains or []),
            )
            dynamic_result["quality_gate"] = quality_gate

            helpers._persist_dynamic_normalized_tables(
                db=db,
                task_id=task_id,
                package_name=package_name,
                exploration_result=exploration_result,
                traffic_monitor=traffic_adapter,
                domain_report=domain_report,
            )
            # Persist child evidence rows before updating the parent task row.
            # These normalized tables all reference tasks.id via FK; writing the
            # parent row in one session while inserting children in another
            # session can self-block under concurrent load.
            task.dynamic_analysis_result = dynamic_result
            task.last_success_stage = "dynamic"
            task.failure_reason = None
            task.error_message = (
                f"degraded:{quality_gate['reason']}"
                if quality_gate["degraded"]
                else None
            )
            finish_stage_run(
                db,
                task_id=task_id,
                stage="dynamic",
                success=True,
                details=helpers._build_dynamic_stage_run_details(
                    emulator={
                    "host": host,
                    "port": port,
                    "lease_backend": "redroid_remote",
                    "slot_name": slot_name,
                },
                    exploration_result=exploration_result,
                    primary_requests=network_requests,
                    candidate_requests=candidate_requests,
                    master_domains=master_domains,
                    quality_gate=quality_gate,
                    network_analysis=dynamic_result.get("network_analysis", {}),
                ),
            )
            helpers._commit_with_retry(db, context="save_redroid_dynamic_result")

            return {
                "task_id": task_id,
                "status": "success",
                "backend": self.backend_name,
                "capture_mode": dynamic_result.get("capture_mode", REDROID_CAPTURE_MODE),
                "exploration_steps": exploration_result.total_steps,
                "screenshots": len(exploration_result.screenshots or []),
                "network_requests": len(network_requests),
                "candidate_requests": len(candidate_requests),
                "master_domains": len(master_domains),
                "quality_gate": quality_gate,
            }
        except Exception as exc:
            logger.error("Redroid remote dynamic analysis failed for task %s: %s", task_id, exc, exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            helpers = _dynamic_helpers()
            helpers._mark_task_failed(task_id, str(exc))
            raise
        finally:
            if traffic_collector and capture:
                try:
                    traffic_collector.stop_capture(capture)
                except Exception as exc:
                    logger.warning("Failed to stop redroid capture task=%s: %s", task_id, exc)
            if slot_name:
                try:
                    RedroidLeaseManager(
                        settings.redroid_slots,
                        ttl_seconds=settings.REDROID_LEASE_TTL_SECONDS,
                        acquire_timeout_seconds=settings.REDROID_LEASE_ACQUIRE_TIMEOUT_SECONDS,
                        poll_interval_seconds=settings.REDROID_LEASE_POLL_INTERVAL_SECONDS,
                    ).release(task_id, slot_name)
                except Exception as exc:
                    logger.warning("Failed to release redroid slot task=%s slot=%s: %s", task_id, slot_name, exc)
            if apk_temp_path and os.path.exists(apk_temp_path):
                try:
                    os.unlink(apk_temp_path)
                except OSError:
                    pass
            db.close()
