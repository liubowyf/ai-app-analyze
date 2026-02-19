"""Whitelist schemas for API request/response models."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from models.whitelist import WhitelistCategory


class WhitelistCreateRequest(BaseModel):
    """Request schema for creating a whitelist rule."""

    domain: str = Field(..., description="Domain pattern (supports wildcard *)")
    ip_range: Optional[str] = Field(None, description="IP range in CIDR format")
    category: WhitelistCategory = Field(..., description="Rule category")
    description: Optional[str] = Field(None, description="Description of the rule")
    is_active: bool = Field(True, description="Whether the rule is active")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "domain": "example.com",
                "ip_range": "192.168.1.0/24",
                "category": "custom",
                "description": "Example whitelist rule",
                "is_active": True,
            }
        }


class WhitelistUpdateRequest(BaseModel):
    """Request schema for updating a whitelist rule."""

    domain: Optional[str] = Field(None, description="Domain pattern (supports wildcard *)")
    ip_range: Optional[str] = Field(None, description="IP range in CIDR format")
    category: Optional[WhitelistCategory] = Field(None, description="Rule category")
    description: Optional[str] = Field(None, description="Description of the rule")
    is_active: Optional[bool] = Field(None, description="Whether the rule is active")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "domain": "updated-example.com",
                "description": "Updated description",
                "is_active": False,
            }
        }


class WhitelistResponse(BaseModel):
    """Response schema for a single whitelist rule."""

    id: str = Field(..., description="Unique rule identifier")
    domain: str = Field(..., description="Domain pattern")
    ip_range: Optional[str] = Field(None, description="IP range in CIDR format")
    category: str = Field(..., description="Rule category")
    description: Optional[str] = Field(None, description="Description of the rule")
    is_active: bool = Field(..., description="Whether the rule is active")
    created_at: str = Field(..., description="Rule creation timestamp")
    updated_at: str = Field(..., description="Rule update timestamp")

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "domain": "example.com",
                "ip_range": "192.168.1.0/24",
                "category": "custom",
                "description": "Example whitelist rule",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        }


class WhitelistListResponse(BaseModel):
    """Response schema for paginated list of whitelist rules."""

    items: List[WhitelistResponse] = Field(..., description="List of whitelist rules")
    total: int = Field(..., description="Total number of rules")
    skip: int = Field(..., description="Number of rules skipped")
    limit: int = Field(..., description="Number of rules per page")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "domain": "example.com",
                        "ip_range": "192.168.1.0/24",
                        "category": "custom",
                        "description": "Example whitelist rule",
                        "is_active": True,
                        "created_at": "2024-01-01T00:00:00",
                        "updated_at": "2024-01-01T00:00:00",
                    }
                ],
                "total": 1,
                "skip": 0,
                "limit": 10,
            }
        }
