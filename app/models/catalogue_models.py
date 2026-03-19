"""
Catalogue data models for request/response handling.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.menu_option_models import MenuOptionGroupResponse


class CatalogueItemCreate(BaseModel):
    """Request model for creating a catalogue item."""

    category: Optional[str] = Field(None, max_length=100, description="Catalogue category (e.g., 'Appetizers', 'Entrees')")
    sub_category: Optional[str] = Field(
        None, max_length=100, description="Catalogue sub-category (e.g., 'Vegetarian', 'Seafood')"
    )
    item_name: str = Field(..., max_length=255, description="Name of the catalogue item")
    item_desc: Optional[str] = Field(None, description="Detailed description of the catalogue item")
    price: Decimal = Field(
        ..., gt=0, le=10000, decimal_places=2, description="Price of the item (must be positive, max $10,000)"
    )
    avg_prep_time: Optional[int] = Field(
        None, ge=0, le=300, description="Average preparation time in minutes (max 300 minutes)"
    )
    suggested_items: Optional[List[int]] = Field(default=None, description="Array of suggested catalogue item IDs")
    is_available: Optional[bool] = Field(True, description="Whether the item is currently available")
    is_special: Optional[bool] = Field(False, description="Whether the item is marked as a special")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Flexible JSON metadata for the item (e.g., location for real estate)")

    model_config = ConfigDict(extra="ignore")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        """Ensure price is positive and within reasonable limit."""
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than 0")
        if v is not None and v > 10000:
            raise ValueError("Price cannot exceed $10,000")
        return v

    @field_validator("avg_prep_time")
    @classmethod
    def validate_prep_time(cls, v):
        """Ensure prep time is within reasonable limit."""
        if v is not None and v < 0:
            raise ValueError("Average prep time cannot be negative")
        if v is not None and v > 300:
            raise ValueError("Average prep time cannot exceed 300 minutes (5 hours)")
        return v

    @field_validator("suggested_items")
    @classmethod
    def validate_suggested_items(cls, v):
        """Remove duplicates from suggested items list."""
        if v is not None:
            # Remove duplicates while preserving order
            seen = set()
            unique_items = []
            for item in v:
                if item not in seen:
                    seen.add(item)
                    unique_items.append(item)
            return unique_items if unique_items else None
        return v

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, v):
        """Ensure item_name is not empty."""
        if v is None or str(v).strip() == "":
            raise ValueError("item_name cannot be empty")
        return str(v).strip()

    @field_validator("is_available", mode="before")
    @classmethod
    def validate_is_available(cls, v):
        """Convert None to default True value when explicitly set to null."""
        if v is None:
            return True
        return v

    @field_validator("is_special", mode="before")
    @classmethod
    def validate_is_special(cls, v):
        """Convert None to default False value when explicitly set to null."""
        if v is None:
            return False
        return v


class CatalogueItemUpdate(BaseModel):
    """Request model for updating a catalogue item (all fields optional)."""

    category: Optional[str] = Field(None, max_length=100, description="Catalogue category")
    sub_category: Optional[str] = Field(None, max_length=100, description="Catalogue sub-category")
    item_name: Optional[str] = Field(None, max_length=255, description="Name of the catalogue item")
    item_desc: Optional[str] = Field(None, description="Detailed description of the catalogue item")
    price: Optional[Decimal] = Field(
        None, gt=0, le=10000, decimal_places=2, description="Price of the item (must be positive, max $10,000)"
    )
    avg_prep_time: Optional[int] = Field(
        None, ge=0, le=300, description="Average preparation time in minutes (max 300 minutes)"
    )
    suggested_items: Optional[List[int]] = Field(None, description="Array of suggested catalogue item IDs")
    is_available: Optional[bool] = Field(None, description="Whether the item is currently available")
    is_special: Optional[bool] = Field(None, description="Whether the item is marked as a special")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Flexible JSON metadata for the item (e.g., location for real estate)")

    model_config = ConfigDict(extra="ignore")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        """Ensure price is positive and within reasonable limit if provided."""
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than 0")
        if v is not None and v > 10000:
            raise ValueError("Price cannot exceed $10,000")
        return v

    @field_validator("avg_prep_time")
    @classmethod
    def validate_prep_time(cls, v):
        """Ensure prep time is within reasonable limit if provided."""
        if v is not None and v < 0:
            raise ValueError("Average prep time cannot be negative")
        if v is not None and v > 300:
            raise ValueError("Average prep time cannot exceed 300 minutes (5 hours)")
        return v

    @field_validator("suggested_items")
    @classmethod
    def validate_suggested_items(cls, v):
        """Remove duplicates from suggested items list."""
        if v is not None:
            # Remove duplicates while preserving order
            seen = set()
            unique_items = []
            for item in v:
                if item not in seen:
                    seen.add(item)
                    unique_items.append(item)
            return unique_items if unique_items else None
        return v

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, v):
        """Ensure item_name is not empty if provided."""
        if v is not None and str(v).strip() == "":
            raise ValueError("item_name cannot be empty")
        return str(v).strip() if v else v


class CatalogueItemResponse(BaseModel):
    """Response model for a catalogue item."""

    id: int = Field(..., description="Unique identifier for the catalogue item")
    business_id: int = Field(..., description="ID of the business this item belongs to")
    business_name: Optional[str] = Field(None, description="Name of the business")
    category: Optional[str] = Field(None, description="Catalogue category")
    sub_category: Optional[str] = Field(None, description="Catalogue sub-category")
    item_name: str = Field(..., description="Name of the catalogue item")
    item_desc: Optional[str] = Field(None, description="Detailed description of the catalogue item")
    price: Decimal = Field(..., description="Price of the item")
    avg_prep_time: Optional[int] = Field(None, description="Average preparation time in minutes")
    suggested_items: Optional[List[int]] = Field(None, description="Array of suggested catalogue item IDs")
    is_available: bool = Field(..., description="Whether the item is currently available")
    is_special: bool = Field(..., description="Whether the item is marked as a special")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Flexible JSON metadata for the item (e.g., location for real estate)")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the item was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the item was last updated")
    option_groups: Optional[List[MenuOptionGroupResponse]] = Field(
        None, description="Customization option groups for the item"
    )

    model_config = ConfigDict(from_attributes=True)


class CatalogueItemsPage(BaseModel):
    """Paginated response for catalogue items."""

    items: List[CatalogueItemResponse] = Field(..., description="List of catalogue items for the current page")
    pagination: Dict[str, Any] = Field(..., description="Pagination metadata")


class ToggleAvailabilityRequest(BaseModel):
    """Request model for toggling item availability."""

    is_available: bool = Field(..., description="New availability status")

    model_config = ConfigDict(extra="ignore")


class ToggleSpecialRequest(BaseModel):
    """Request model for toggling special status."""

    is_special: bool = Field(..., description="New special status")

    model_config = ConfigDict(extra="ignore")


class BulkAvailabilityRequest(BaseModel):
    """Request model for bulk updating availability."""

    catalogue_item_ids: List[int] = Field(..., min_length=1, description="List of catalogue item IDs to update")
    is_available: bool = Field(..., description="New availability status for all items")

    model_config = ConfigDict(extra="ignore")


class CatalogueCategoriesResponse(BaseModel):
    """Response model for catalogue categories."""

    categories: Dict[str, List[str]] = Field(
        ..., description="Dictionary with categories as keys and arrays of sub-categories as values"
    )
