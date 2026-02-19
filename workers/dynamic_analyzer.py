"""Dynamic analysis Celery task."""
import logging
from typing import Optional

from celery import shared_task
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.android_runner import AndroidRunner
from modules.traffic_monitor import TrafficMonitor
from modules.ai_driver import AIDriver

logger = logging.getLogger(__name__)


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
    container_id: Optional[str] = None

    try:
        # Get task from database
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

        # Initialize components
        android_runner = AndroidRunner()
        traffic_monitor = TrafficMonitor()
        traffic_monitor.set_whitelist(whitelist_domains)

        ai_driver = AIDriver()

        # Create Android container
        container_id = android_runner.create_container(
            name=f"apk-analysis-{task_id[:8]}"
        )

        # Wait for container to start
        import time
        time.sleep(30)  # Wait for emulator to boot

        # Install APK
        # Download APK from MinIO
        apk_content = storage_client.download_file(task.apk_storage_path)

        # Save APK to temporary location in container
        # Note: In real implementation, would mount volume or use API
        logger.info(f"Container {container_id} ready for APK installation")

        # Start traffic monitoring
        traffic_monitor.start()

        # Run AI-driven analysis
        analysis_steps = []
        max_steps = 10

        for step in range(max_steps):
            logger.info(f"Running analysis step {step + 1}/{max_steps}")

            # Take screenshot (placeholder - real implementation would capture from container)
            screenshot_data = b""

            # Analyze and decide
            operation = ai_driver.analyze_and_decide(
                screenshot_data,
                analysis_steps,
                goal="Explore app, trigger network requests"
            )

            # Execute operation
            op_data = ai_driver.execute_operation(operation)

            # Record step
            analysis_steps.append({
                "step": step + 1,
                "operation": operation.type.value,
                "description": operation.description,
                "result": "success",
            })

            # Check if we've captured enough data
            if len(traffic_monitor.requests) >= 5:
                break

            # Wait between steps
            time.sleep(2)

        # Stop monitoring
        traffic_monitor.stop()

        # Get analysis results
        network_analysis = traffic_monitor.analyze_traffic()
        suspicious_requests = [
            {
                "url": req.url,
                "method": req.method,
                "host": req.host,
                "ip": req.ip,
                "response_code": req.response_code,
            }
            for req in traffic_monitor.get_suspicious_requests()
        ]

        # Store results
        task.dynamic_analysis_result = {
            "steps": analysis_steps,
            "network_analysis": network_analysis,
            "suspicious_requests": suspicious_requests,
        }
        db.commit()

        logger.info(f"Dynamic analysis completed for task {task_id}")

        return {
            "task_id": task_id,
            "status": "success",
            "network_requests": len(suspicious_requests),
        }

    except Exception as e:
        logger.error(f"Dynamic analysis failed for task {task_id}: {e}")
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise

    finally:
        # Cleanup
        if container_id:
            try:
                android_runner = AndroidRunner()
                android_runner.stop_container(container_id)
                android_runner.remove_container(container_id, force=True)
            except Exception as e:
                logger.error(f"Failed to cleanup container: {e}")

        db.close()
