"""Whitelist model for network filtering."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, Index, String
from sqlalchemy.orm import Mapped

from core.database import Base


class WhitelistCategory(str, Enum):
    """Whitelist category enum."""

    SYSTEM = "system"
    CDN = "cdn"
    ANALYTICS = "analytics"
    ADS = "ads"
    THIRD_PARTY = "third_party"
    CUSTOM = "custom"


class WhitelistRule(Base):
    """
    Whitelist rule model for network filtering.

    Attributes:
        id: Unique rule identifier (UUID format)
        domain: Domain pattern (supports wildcard *)
        ip_range: IP range in CIDR format (optional)
        category: Rule category for classification
        description: Description of the rule
        is_active: Whether the rule is active
        created_at: Rule creation timestamp
        updated_at: Rule update timestamp
    """

    __tablename__ = "whitelist_rules"

    # Primary key
    id: Mapped[str] = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Domain and IP information
    domain: Mapped[str] = Column(
        String(255), nullable=False, index=True, comment="Domain pattern (supports wildcard *)"
    )
    ip_range: Mapped[Optional[str]] = Column(
        String(50), nullable=True, comment="IP range in CIDR format"
    )

    # Category and metadata
    category: Mapped[WhitelistCategory] = Column(
        String(20), nullable=False, index=True, comment="Rule category"
    )
    description: Mapped[Optional[str]] = Column(
        String(500), nullable=True, comment="Description of the rule"
    )

    # Status
    is_active: Mapped[bool] = Column(
        Boolean, default=True, nullable=False, index=True, comment="Whether the rule is active"
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Add explicit indexes
    __table_args__ = (
        Index("idx_whitelist_domain", "domain"),
        Index("idx_whitelist_category", "category"),
        Index("idx_whitelist_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        """
        Return string representation of WhitelistRule.

        Returns:
            String representation with rule ID, domain, and category
        """
        category = self.category.value if hasattr(self.category, 'value') else self.category
        return (
            f"<WhitelistRule(id={self.id}, "
            f"domain={self.domain}, "
            f"category={category})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert whitelist rule to dictionary.

        Returns:
            Dictionary with rule data and ISO formatted timestamps
        """
        category = self.category.value if hasattr(self.category, 'value') else self.category
        result = {
            "id": self.id,
            "domain": self.domain,
            "ip_range": self.ip_range,
            "category": category if category else None,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        return result
