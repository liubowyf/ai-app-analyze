"""Static analysis stage service."""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus
from modules.apk_analyzer.analyzer import ApkAnalyzer
from modules.task_orchestration.run_tracker import finish_stage_run, start_stage_run

logger = logging.getLogger(__name__)


def run_static_analysis(task_id: str) -> dict:
    """Static stage entrypoint."""
    from modules.task_orchestration.stage_services import run_static_stage

    return run_static_stage(task_id)


def _run_static_stage_impl(task_id: str) -> dict:
    """
    Run static analysis on an APK file.

    Args:
        task_id: Task ID to process

    Returns:
        Analysis result dict
    """
    db: Session = SessionLocal()
    task = None
    try:
        # Get task from database
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        task.status = TaskStatus.STATIC_ANALYZING
        start_stage_run(db, task_id=task_id, stage="static")
        db.commit()

        logger.info(f"Starting static analysis for task {task_id}")

        # Download APK from MinIO
        apk_content = storage_client.download_file(task.apk_storage_path)

        # Check if APK is packed/encrypted
        if _is_packed_apk(apk_content):
            logger.warning(f"APK {task_id} is packed/encrypted, skipping static analysis")
            task.static_analysis_result = {
                "is_packed": True,
                "message": "APK is packed/encrypted. Static analysis skipped, proceeding to dynamic analysis."
            }
            finish_stage_run(
                db,
                task_id=task_id,
                stage="static",
                success=True,
                details={"status": "skipped_packed"},
            )
            db.commit()

            logger.info(f"Skipping static analysis for packed APK {task_id}")

            return {
                "task_id": task_id,
                "status": "skipped",
                "reason": "APK is packed/encrypted"
            }

        # Run analysis
        analyzer = ApkAnalyzer()
        result = analyzer.analyze(
            apk_content=apk_content,
            file_size=task.apk_file_size,
            md5=task.apk_md5,
        )
        if analyzer.icon_bytes:
            content_type = analyzer.icon_content_type or "image/png"
            extension = ".png"
            if content_type == "image/webp":
                extension = ".webp"
            elif content_type == "image/jpeg":
                extension = ".jpg"
            icon_storage_path = f"icons/{task_id}/app-icon{extension}"
            if storage_client.upload_file(icon_storage_path, analyzer.icon_bytes, content_type):
                result.basic_info.icon_storage_path = icon_storage_path
                result.basic_info.icon_content_type = content_type

        # Store results - convert datetime to string for JSON serialization
        result_dict = result.model_dump()
        # Convert any datetime objects to ISO format strings
        def convert_datetime(obj):
            """递归转换datetime对象为字符串"""
            if isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            elif hasattr(obj, 'isoformat'):
                return obj.isoformat()
            else:
                return obj

        result_dict = convert_datetime(result_dict)

        task.static_analysis_result = result_dict
        finish_stage_run(
            db,
            task_id=task_id,
            stage="static",
            success=True,
            details={"status": "success", "package_name": result.basic_info.package_name},
        )
        db.commit()

        logger.info(f"Static analysis completed for task {task_id}")

        return {
            "task_id": task_id,
            "status": "success",
            "package_name": result.basic_info.package_name,
        }

    except Exception as e:
        logger.error(f"Static analysis failed for task {task_id}: {e}")
        if task:
            # 标记静态分析失败,但不影响后续动态分析
            task.static_analysis_result = {
                "error": True,
                "message": f"Static analysis failed: {str(e)}. Proceeding to dynamic analysis.",
                "is_packed": "AndroidManifest.xml" in str(e) or "encrypted" in str(e).lower()
            }
            finish_stage_run(
                db,
                task_id=task_id,
                stage="static",
                success=False,
                error_message=str(e),
                details={"status": "failed"},
            )
            db.commit()
            logger.info(f"Static analysis failed but proceeding to dynamic analysis for task {task_id}")

        # 返回跳过状态,不抛出异常
        return {
            "task_id": task_id,
            "status": "failed",
            "reason": str(e)
        }
    finally:
        db.close()


def _is_packed_apk(apk_content: bytes) -> bool:
    """
    Check if APK is packed or encrypted.

    Args:
        apk_content: APK file content

    Returns:
        bool: True if APK is packed/encrypted
    """
    import zipfile
    import io

    try:
        # Try to open APK as zip file
        with zipfile.ZipFile(io.BytesIO(apk_content), 'r') as zf:
            # Check if AndroidManifest.xml can be read
            # In packed APKs, this file is usually encrypted
            try:
                manifest_data = zf.read('AndroidManifest.xml')

                # Check for encryption indicators
                # Normal AndroidManifest.xml is binary XML starting with specific bytes
                # Packed APKs may have encrypted data
                if len(manifest_data) > 0:
                    # Check if it's encrypted (not valid binary XML)
                    # Binary XML starts with 0x0003 (version) followed by specific patterns
                    if not _is_valid_binary_xml(manifest_data):
                        logger.warning("AndroidManifest.xml appears to be encrypted")
                        return True

            except Exception as e:
                # If we can't read the manifest, it's likely packed
                logger.warning(f"Cannot read AndroidManifest.xml: {e}")
                return True

        return False

    except Exception as e:
        logger.error(f"Error checking if APK is packed: {e}")
        # If we can't determine, assume it's not packed to allow analysis attempt
        return False


def _is_valid_binary_xml(data: bytes) -> bool:
    """
    Check if data is valid Android binary XML.

    Args:
        data: Binary data to check

    Returns:
        bool: True if data appears to be valid binary XML
    """
    if len(data) < 4:
        return False

    # Android binary XML starts with:
    # 0x0003 - version (2 bytes)
    # 0x0008 - file size (2 bytes) or other header data
    # Check for common binary XML patterns

    # Normal binary XML markers
    # First 2 bytes should be 0x0003 (version) or similar
    # Third and fourth bytes usually indicate file structure

    # Simple heuristic: check if first few bytes look like binary XML
    # Binary XML typically starts with small version numbers
    if data[0] == 0x03 and data[1] == 0x00:
        return True

    # Some APKs may have different formats
    # Check for typical XML structure markers
    if data[:4] in [b'\x03\x00\x08\x00', b'\x03\x00\x00\x00']:
        return True

    # If data appears random/encrypted (high entropy), it's likely packed
    # Simple entropy check: count unique bytes
    unique_bytes = len(set(data[:256]))
    if unique_bytes > 200:  # High entropy suggests encryption
        return False

    return True
