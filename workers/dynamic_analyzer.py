"""Dynamic analysis Celery task."""
import json
import logging
from typing import Optional, Dict
import tempfile
import os
import time

from celery import shared_task
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from core.config import settings
from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.android_runner import AndroidRunner
from modules.traffic_monitor import TrafficMonitor
from modules.ai_driver import AIDriver
from modules.screenshot_manager.manager import ScreenshotManager
from modules.exploration_strategy.explorer import AppExplorer
from modules.exploration_strategy.policy import ExplorationPolicy
from modules.domain_analyzer.analyzer import MasterDomainAnalyzer

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
        _commit_with_retry(fail_db, context="mark_task_failed")
    except Exception as exc:
        logger.error("Failed to persist task failure status for %s: %s", task_id, exc)
    finally:
        fail_db.close()

def _build_emulator_pool() -> list[dict]:
    """Build emulator pool from .env, prioritizing emulator_4 when configured."""
    preferred = [
        settings.ANDROID_EMULATOR_4,
        settings.ANDROID_EMULATOR_1,
        settings.ANDROID_EMULATOR_2,
        settings.ANDROID_EMULATOR_3,
    ]
    seen = set()
    pool = []
    for item in preferred:
        if not item or item in seen or ":" not in item:
            continue
        seen.add(item)
        host, port_raw = item.rsplit(":", 1)
        try:
            port = int(port_raw)
        except ValueError:
            logger.warning("Skip invalid emulator config: %s", item)
            continue
        pool.append({"host": host, "port": port, "in_use": False})

    if not pool:
        pool = [{"host": "10.16.148.66", "port": 5558, "in_use": False}]
    return pool


# Remote emulator pool configuration
EMULATOR_POOL = _build_emulator_pool()


def get_available_emulator() -> Optional[Dict]:
    """
    Get an available emulator from the pool (simple load balancing).

    Returns:
        Emulator config dict or None if all are busy
    """
    for emulator in EMULATOR_POOL:
        if not emulator["in_use"]:
            emulator["in_use"] = True
            logger.info(f"Allocated emulator {emulator['host']}:{emulator['port']}")
            return emulator
    logger.warning("No available emulators in pool")
    return None


def release_emulator(emulator: Dict) -> None:
    """
    Release an emulator back to the pool.

    Args:
        emulator: Emulator config dict
    """
    emulator["in_use"] = False
    logger.info(f"Released emulator {emulator['host']}:{emulator['port']}")


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
        },
        "network_analysis": traffic_monitor.analyze_traffic(),
        "suspicious_requests": traffic_monitor.get_requests_as_dict()[:max_requests],
        "network_aggregated": traffic_monitor.get_aggregated_requests()[:200],
        "master_domains": domain_report,
    }


@shared_task(bind=True, name="workers.dynamic_analyzer.run_dynamic_analysis")
def run_dynamic_analysis(self, task_id: str) -> dict:
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
    apk_temp_path: Optional[str] = None

    try:
        # 1. Get Task
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        task.status = TaskStatus.DYNAMIC_ANALYZING
        _commit_with_retry(db, context="set_dynamic_analyzing")

        logger.info(f"Starting dynamic analysis for task {task_id}")

        # Get whitelist from database
        from models.whitelist import WhitelistRule
        whitelist_rules = db.query(WhitelistRule).filter(
            WhitelistRule.is_active == True
        ).all()
        whitelist_domains = [rule.domain for rule in whitelist_rules]

        # 2. Select available emulator
        emulator = get_available_emulator()
        if not emulator:
            raise RuntimeError("No available emulators in pool")

        host = emulator["host"]
        port = emulator["port"]

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
            from androguard.misc import AnalyzeAPK

            try:
                a, d, dx = AnalyzeAPK(apk_temp_path)
                package_name = a.get_package()
                logger.info(f"Package name extracted: {package_name}")
            except Exception as e:
                logger.warning(f"Failed to extract package name (APK may be packed): {e}")
                logger.info("Proceeding without package name - will use APK filename for installation")
                # 尝试从APK文件名推断包名,或者设置为None让后续流程处理
                package_name = None

        # package_name可以为None,后续install_apk_remote会处理
        if package_name:
            logger.info(f"Using package name: {package_name}")
        else:
            logger.warning("No package name available, proceeding with dynamic analysis anyway")

        # 4. Create ScreenshotManager instance
        screenshot_manager = ScreenshotManager(task_id=task_id)

        # Initialize components
        traffic_monitor = TrafficMonitor()
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

        task.dynamic_analysis_result = dynamic_result
        _commit_with_retry(db, context="save_dynamic_result")

        logger.info(f"Dynamic analysis completed for task {task_id}")

        return {
            "task_id": task_id,
            "status": "success",
            "exploration_steps": exploration_result.total_steps,
            "screenshots": len(exploration_result.screenshots),
            "network_requests": len(network_requests),
            "master_domains": len(master_domains),
        }

    except Exception as e:
        logger.error(f"Dynamic analysis failed for task {task_id}: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        _mark_task_failed(task_id, str(e))
        raise

    finally:
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
