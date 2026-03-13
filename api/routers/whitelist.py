"""Whitelist router for managing whitelist rules."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.schemas.whitelist import (
    WhitelistCreateRequest,
    WhitelistUpdateRequest,
    WhitelistResponse,
    WhitelistListResponse,
)
from core.database import get_db
from models.whitelist import WhitelistCategory, WhitelistRule

router = APIRouter()


@router.get("/", response_model=WhitelistListResponse)
def list_whitelist_rules(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    category: Optional[WhitelistCategory] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
):
    """
    List whitelist rules with pagination and optional filters.

    Args:
        skip: Number of items to skip for pagination
        limit: Maximum number of items to return
        category: Optional category filter
        is_active: Optional active status filter
        db: Database session

    Returns:
        Paginated list of whitelist rules
    """
    query = db.query(WhitelistRule)

    # Apply filters
    if category is not None:
        query = query.filter(WhitelistRule.category == category)
    if is_active is not None:
        query = query.filter(WhitelistRule.is_active == is_active)

    # Get total count
    total = query.count()

    # Apply pagination
    rules = query.offset(skip).limit(limit).all()

    # Convert to response format
    items = [WhitelistResponse(**rule.to_dict()) for rule in rules]

    return WhitelistListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/",
    response_model=WhitelistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_whitelist_rule(
    rule_data: WhitelistCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new whitelist rule.

    Args:
        rule_data: Whitelist rule creation data
        db: Database session

    Returns:
        Created whitelist rule
    """
    # Create new rule
    new_rule = WhitelistRule(
        domain=rule_data.domain,
        ip_range=rule_data.ip_range,
        category=rule_data.category,
        description=rule_data.description,
        is_active=rule_data.is_active,
    )

    # Save to database
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    return WhitelistResponse(**new_rule.to_dict())


@router.get("/{rule_id}", response_model=WhitelistResponse)
def get_whitelist_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    """
    Get a specific whitelist rule by ID.

    Args:
        rule_id: Unique identifier of the whitelist rule
        db: Database session

    Returns:
        Whitelist rule details

    Raises:
        HTTPException: 404 if rule not found
    """
    rule = db.query(WhitelistRule).filter(WhitelistRule.id == rule_id).first()

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Whitelist rule with id {rule_id} not found",
        )

    return WhitelistResponse(**rule.to_dict())


@router.put("/{rule_id}", response_model=WhitelistResponse)
def update_whitelist_rule(
    rule_id: str,
    rule_data: WhitelistUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update a whitelist rule.

    Args:
        rule_id: Unique identifier of the whitelist rule
        rule_data: Whitelist rule update data
        db: Database session

    Returns:
        Updated whitelist rule

    Raises:
        HTTPException: 404 if rule not found
    """
    # Find the rule
    rule = db.query(WhitelistRule).filter(WhitelistRule.id == rule_id).first()

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Whitelist rule with id {rule_id} not found",
        )

    # Update fields that are provided
    update_dict = rule_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(rule, field, value)

    # Save changes
    db.commit()
    db.refresh(rule)

    return WhitelistResponse(**rule.to_dict())


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_whitelist_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a whitelist rule.

    Args:
        rule_id: Unique identifier of the whitelist rule
        db: Database session

    Raises:
        HTTPException: 404 if rule not found
    """
    # Find the rule
    rule = db.query(WhitelistRule).filter(WhitelistRule.id == rule_id).first()

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Whitelist rule with id {rule_id} not found",
        )

    # Delete the rule
    db.delete(rule)
    db.commit()

    return None
