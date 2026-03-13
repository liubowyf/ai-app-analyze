"""APK Pydantic schemas for API request/response models."""
from pydantic import BaseModel, Field


class APKUploadResponse(BaseModel):
    """Response schema for APK file upload."""

    task_id: str = Field(..., description="Unique task identifier")
    file_name: str = Field(..., description="Original APK file name")
    file_size: int = Field(..., description="APK file size in bytes")
    md5: str = Field(..., description="MD5 hash of the APK file")
    message: str = Field(..., description="Upload status message")

    class Config:
        """Pydantic config for schema."""

        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "file_name": "sample.apk",
                "file_size": 1024000,
                "md5": "5d41402abc4b2a76b9719d911017c592",
                "message": "APK file uploaded successfully",
            }
        }
