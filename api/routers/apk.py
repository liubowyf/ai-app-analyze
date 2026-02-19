"""APK router for handling APK file upload operations."""
import hashlib
from typing import IO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.schemas.apk import APKUploadResponse
from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskPriority, TaskStatus

router = APIRouter()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_md5(file_content: bytes) -> str:
    """
    Calculate MD5 hash of file content.

    Args:
        file_content: File content as bytes

    Returns:
        MD5 hash as hexadecimal string
    """
    return hashlib.md5(file_content).hexdigest()


def validate_apk_file(filename: str) -> None:
    """
    Validate that file has .apk extension.

    Args:
        filename: Name of the file to validate

    Raises:
        HTTPException: If file doesn't have .apk extension
    """
    if not filename or not filename.lower().endswith(".apk"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Only .apk files are allowed.",
        )


@router.post("/upload", response_model=APKUploadResponse, status_code=status.HTTP_200_OK)
async def upload_apk(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> APKUploadResponse:
    """
    Upload APK file for analysis.

    This endpoint:
    - Validates the file extension (.apk)
    - Calculates MD5 hash
    - Stores the file in MinIO
    - Creates a Task record in database

    Args:
        file: Uploaded APK file
        db: Database session dependency

    Returns:
        APKUploadResponse with task_id and file information

    Raises:
        HTTPException: 400 for invalid file, 500 for storage failure
    """
    # Validate file extension
    validate_apk_file(file.filename)

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Calculate MD5 hash
    md5_hash = calculate_md5(file_content)

    # Create task record
    task = Task(
        apk_file_name=file.filename,
        apk_file_size=file_size,
        apk_md5=md5_hash,
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
    )

    # Generate storage path
    storage_path = storage_client.generate_apk_path(task.id, md5_hash)

    # Upload file to MinIO
    upload_success = storage_client.upload_file(
        object_name=storage_path,
        data=file_content,
        content_type="application/vnd.android.package-archive",
    )

    if not upload_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store file in storage system.",
        )

    # Update task with storage path
    task.apk_storage_path = storage_path

    # Save task to database
    db.add(task)
    db.commit()
    db.refresh(task)

    # Return response
    return APKUploadResponse(
        task_id=task.id,
        file_name=task.apk_file_name,
        file_size=task.apk_file_size,
        md5=task.apk_md5,
        message="APK file uploaded successfully",
    )
