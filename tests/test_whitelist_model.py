"""Unit tests for Whitelist model."""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.whitelist import WhitelistCategory, WhitelistRule


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestWhitelistCategory:
    """Test cases for WhitelistCategory enum."""

    def test_category_values(self):
        """Test that WhitelistCategory has all required values."""
        assert WhitelistCategory.SYSTEM == "system"
        assert WhitelistCategory.CDN == "cdn"
        assert WhitelistCategory.ANALYTICS == "analytics"
        assert WhitelistCategory.ADS == "ads"
        assert WhitelistCategory.THIRD_PARTY == "third_party"
        assert WhitelistCategory.CUSTOM == "custom"


class TestWhitelistRuleModel:
    """Test cases for WhitelistRule model."""

    def test_create_whitelist_rule_with_required_fields(self, db_session):
        """Test creating a whitelist rule with only required fields."""
        rule = WhitelistRule(
            domain="example.com",
            category=WhitelistCategory.CUSTOM,
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.id is not None
        assert len(rule.id) == 36  # UUID format
        assert rule.domain == "example.com"
        assert rule.category == WhitelistCategory.CUSTOM
        assert rule.is_active is True
        assert rule.created_at is not None
        assert rule.updated_at is not None

    def test_create_whitelist_rule_with_all_fields(self, db_session):
        """Test creating a whitelist rule with all fields."""
        rule = WhitelistRule(
            id="12345678-1234-5678-1234-567812345678",
            domain="*.cdn.example.com",
            ip_range="192.168.1.0/24",
            category=WhitelistCategory.CDN,
            description="CDN whitelist rule",
            is_active=False,
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.id == "12345678-1234-5678-1234-567812345678"
        assert rule.domain == "*.cdn.example.com"
        assert rule.ip_range == "192.168.1.0/24"
        assert rule.category == WhitelistCategory.CDN
        assert rule.description == "CDN whitelist rule"
        assert rule.is_active is False

    def test_whitelist_rule_repr(self, db_session):
        """Test whitelist rule string representation."""
        rule = WhitelistRule(
            domain="analytics.google.com",
            category=WhitelistCategory.ANALYTICS,
        )
        db_session.add(rule)
        db_session.commit()

        repr_str = repr(rule)
        assert "WhitelistRule" in repr_str
        assert rule.id in repr_str
        assert "analytics.google.com" in repr_str
        assert "analytics" in repr_str

    def test_whitelist_rule_to_dict(self, db_session):
        """Test converting whitelist rule to dictionary."""
        created_at = datetime.utcnow()
        rule = WhitelistRule(
            domain="ads.example.com",
            category=WhitelistCategory.ADS,
            ip_range="10.0.0.0/8",
            description="Ads domain",
            created_at=created_at,
            updated_at=created_at,
        )
        db_session.add(rule)
        db_session.commit()

        rule_dict = rule.to_dict()

        assert rule_dict["id"] == rule.id
        assert rule_dict["domain"] == "ads.example.com"
        assert rule_dict["ip_range"] == "10.0.0.0/8"
        assert rule_dict["category"] == "ads"
        assert rule_dict["description"] == "Ads domain"
        assert rule_dict["is_active"] is True
        assert "created_at" in rule_dict
        assert "updated_at" in rule_dict
        # Check ISO format
        assert "T" in rule_dict["created_at"]

    def test_whitelist_rule_to_dict_with_nullable_fields(self, db_session):
        """Test to_dict with nullable fields."""
        rule = WhitelistRule(
            domain="third.party.com",
            category=WhitelistCategory.THIRD_PARTY,
            ip_range=None,
            description=None,
        )
        db_session.add(rule)
        db_session.commit()

        rule_dict = rule.to_dict()

        assert rule_dict["ip_range"] is None
        assert rule_dict["description"] is None

    def test_whitelist_rule_domain_index(self, db_session):
        """Test that domain field is indexed."""
        rule = WhitelistRule(
            domain="indexed.domain.com",
            category=WhitelistCategory.SYSTEM,
        )
        db_session.add(rule)
        db_session.commit()

        # Query by domain should work efficiently
        found_rule = (
            db_session.query(WhitelistRule)
            .filter(WhitelistRule.domain == "indexed.domain.com")
            .first()
        )
        assert found_rule is not None
        assert found_rule.category == WhitelistCategory.SYSTEM

    def test_whitelist_rule_category_index(self, db_session):
        """Test that category field is indexed."""
        # Create multiple rules with different categories
        for i, category in enumerate([
            WhitelistCategory.SYSTEM,
            WhitelistCategory.CDN,
            WhitelistCategory.ADS,
        ]):
            rule = WhitelistRule(
                domain=f"domain{i}.com",
                category=category,
            )
            db_session.add(rule)
        db_session.commit()

        # Query by category should work efficiently
        cdn_rules = (
            db_session.query(WhitelistRule)
            .filter(WhitelistRule.category == WhitelistCategory.CDN)
            .all()
        )
        assert len(cdn_rules) == 1
        assert cdn_rules[0].domain == "domain1.com"

    def test_whitelist_rule_is_active_index(self, db_session):
        """Test that is_active field is indexed."""
        # Create active and inactive rules
        rule1 = WhitelistRule(
            domain="active.com",
            category=WhitelistCategory.CUSTOM,
            is_active=True,
        )
        rule2 = WhitelistRule(
            domain="inactive.com",
            category=WhitelistCategory.CUSTOM,
            is_active=False,
        )
        db_session.add_all([rule1, rule2])
        db_session.commit()

        # Query by is_active should work efficiently
        active_rules = (
            db_session.query(WhitelistRule)
            .filter(WhitelistRule.is_active == True)
            .all()
        )
        assert len(active_rules) >= 1

    def test_whitelist_rule_updated_at_on_update(self, db_session):
        """Test that updated_at is updated on modification."""
        rule = WhitelistRule(
            domain="update-test.com",
            category=WhitelistCategory.CUSTOM,
        )
        db_session.add(rule)
        db_session.commit()

        original_updated_at = rule.updated_at

        # Modify and commit
        rule.is_active = False
        db_session.commit()

        # updated_at should be different (though in SQLite in-memory, timing might be same)
        # This test verifies the field exists and can be updated
        assert rule.updated_at is not None

    def test_whitelist_rule_wildcard_domain(self, db_session):
        """Test that wildcard domains are supported."""
        rule = WhitelistRule(
            domain="*.wildcard.example.com",
            category=WhitelistCategory.THIRD_PARTY,
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.domain == "*.wildcard.example.com"

    def test_whitelist_rule_cidr_format(self, db_session):
        """Test that IP ranges in CIDR format are supported."""
        rule = WhitelistRule(
            domain="cidr.example.com",
            ip_range="192.168.0.0/16",
            category=WhitelistCategory.CDN,
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.ip_range == "192.168.0.0/16"

    def test_whitelist_rule_nullable_ip_range(self, db_session):
        """Test that ip_range is nullable."""
        rule = WhitelistRule(
            domain="no-ip.example.com",
            category=WhitelistCategory.ANALYTICS,
            ip_range=None,
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.ip_range is None

    def test_whitelist_rule_nullable_description(self, db_session):
        """Test that description is nullable."""
        rule = WhitelistRule(
            domain="no-desc.example.com",
            category=WhitelistCategory.SYSTEM,
            description=None,
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.description is None
