"""Dynamic analysis Celery task."""
import logging
from typing import Optional, Dict
import tempfile
import os

from celery import shared_task
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.android_runner import AndroidRunner
from modules.traffic_monitor import TrafficMonitor
from modules.ai_driver import AIDriver
from modules.screenshot_manager.manager import ScreenshotManager
from modules.exploration_strategy.explorer import AppExplorer
from modules.domain_analyzer.analyzer import MasterDomainAnalyzer

logger = logging.getLogger(__name__)

# Remote emulator pool configuration
EMULATOR_POOL = [
    {"host": "10.16.148.66", "port": 5555, "in_use": False},
    {"host": "10.16.148.66", "port": 5556, "in_use": False},
    {"host": "10.16.148.66", "port": 5557, "in_use": False},
    {"host": "10.16.148.66", "port": 5558, "in_use": False},
]


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
    emulator: Optional[Dict] = None
    apk_temp_path: Optional[str] = None

    try:
        # 1. Get Task
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        task.status = TaskStatus.DYNAMIC_ANALYZING
        db.commit()

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

        # If no package name from static analysis, extract it from APK
        if not package_name:
            logger.info("Extracting package name from APK (no static analysis result)")
            from androguard.misc import AnalyzeAPK

            try:
                a, d, dx = AnalyzeAPK(apk_temp_path)
                package_name = a.get_package()
                logger.info(f"Package name extracted: {package_name}")
            except Exception as e:
                logger.error(f"Failed to extract package name: {e}")
                raise ValueError(f"Failed to extract package name from APK: {e}")

        if not package_name:
            raise ValueError("Package name not found")

        # 4. Create ScreenshotManager instance
        screenshot_manager = ScreenshotManager(task_id=task_id)

        # Initialize components
        traffic_monitor = TrafficMonitor()
        traffic_monitor.set_whitelist(whitelist_domains)

        ai_driver = AIDriver()

        # 5. Create AppExplorer instance
        app_explorer = AppExplorer(
            ai_driver=ai_driver,
            android_runner=android_runner,
            screenshot_manager=screenshot_manager
        )

        # Start traffic monitoring with emulator info
        traffic_monitor.start(emulator_host=host, emulator_port=port)

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
        task.dynamic_analysis_result = {
            "exploration_result": {
                "total_steps": exploration_result.total_steps,
                "screenshots": exploration_result.screenshots,
                "activities_visited": exploration_result.activities_visited,
                "success": exploration_result.success,
                "error_message": exploration_result.error_message,
                "phases_completed": exploration_result.phases_completed,
            },
            "network_analysis": traffic_monitor.analyze_traffic(),
            "suspicious_requests": traffic_monitor.get_requests_as_dict(),
            "master_domains": domain_report,
        }
        db.commit()

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
        if 'task' in locals() and task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
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
