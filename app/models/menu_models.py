"""
Menu data models for request/response handling.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MenuItemCreate(BaseModel):
    """Request model for creating a menu item."""

    category: Optional[str] = Field(None, max_length=100, description="Menu category (e.g., 'Appetizers', 'Entrees')")
    sub_category: Optional[str] = Field(
        None, max_length=100, description="Menu sub-category (e.g., 'Vegetarian', 'Seafood')"
    )
    item_name: str = Field(..., max_length=255, description="Name of the menu item")
    item_desc: Optional[str] = Field(None, description="Detailed description of the menu item")
    price: Decimal = Field(..., gt=0, decimal_places=2, description="Price of the item (must be positive)")
    avg_prep_time: Optional[int] = Field(None, ge=0, description="Average preparation time in minutes")
    suggested_items: Optional[List[int]] = Field(default=None, description="Array of suggested menu item IDs")
    is_available: Optional[bool] = Field(True, description="Whether the item is currently available")
    is_special: Optional[bool] = Field(False, description="Whether the item is marked as a special")

    model_config = ConfigDict(extra="ignore")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        """Ensure price is positive."""
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than 0")
        return v

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, v):
        """Ensure item_name is not empty."""
        if v is None or str(v).strip() == "":
            raise ValueError("item_name cannot be empty")
        return str(v).strip()


class MenuItemUpdate(BaseModel):
    """Request model for updating a menu item (all fields optional)."""

    category: Optional[str] = Field(None, max_length=100, description="Menu category")
    sub_category: Optional[str] = Field(None, max_length=100, description="Menu sub-category")
    item_name: Optional[str] = Field(None, max_length=255, description="Name of the menu item")
    item_desc: Optional[str] = Field(None, description="Detailed description of the menu item")
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2, description="Price of the item (must be positive)")
    avg_prep_time: Optional[int] = Field(None, ge=0, description="Average preparation time in minutes")
    suggested_items: Optional[List[int]] = Field(None, description="Array of suggested menu item IDs")
    is_available: Optional[bool] = Field(None, description="Whether the item is currently available")
    is_special: Optional[bool] = Field(None, description="Whether the item is marked as a special")

    model_config = ConfigDict(extra="ignore")

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        """Ensure price is positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than 0")
        return v

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, v):
        """Ensure item_name is not empty if provided."""
        if v is not None and str(v).strip() == "":
            raise ValueError("item_name cannot be empty")
        return str(v).strip() if v else v


class MenuItemData(BaseModel):
    """Data model for a menu item."""

    id: int = Field(..., description="Unique identifier for the menu item")
    restaurant_id: int = Field(..., description="ID of the restaurant this item belongs to")
    restaurant_name: Optional[str] = Field(None, description="Name of the restaurant")
    category: Optional[str] = Field(None, description="Menu category")
    sub_category: Optional[str] = Field(None, description="Menu sub-category")
    item_name: str = Field(..., description="Name of the menu item")
    item_desc: Optional[str] = Field(None, description="Detailed description of the menu item")
    price: Decimal = Field(..., description="Price of the item")
    avg_prep_time: Optional[int] = Field(None, description="Average preparation time in minutes")
    suggested_items: Optional[List[int]] = Field(None, description="Array of suggested menu item IDs")
    is_available: bool = Field(..., description="Whether the item is currently available")
    is_special: bool = Field(..., description="Whether the item is marked as a special")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the item was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the item was last updated")

    model_config = ConfigDict(from_attributes=True)


class MenuItemResponse(BaseModel):
    """Response wrapper for a single menu item operation."""

    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation result")
    data: MenuItemData = Field(..., description="The menu item data")


class MenuItemsPage(BaseModel):
    """Paginated response for menu items."""

    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation result")
    items: List[MenuItemData] = Field(..., description="List of menu items for the current page")
    pagination: Dict[str, Any] = Field(..., description="Pagination metadata")


class MenuItemDeleteResponse(BaseModel):
    """Response model for menu item deletion."""

    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation result")
    menu_id: int = Field(..., description="ID of the deleted menu item")


class BulkAvailabilityResponse(BaseModel):
    """Response model for bulk availability update."""

    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation result")
    updated_count: int = Field(..., description="Number of menu items updated")


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

    menu_item_ids: List[int] = Field(..., min_length=1, description="List of menu item IDs to update")
    is_available: bool = Field(..., description="New availability status for all items")

    model_config = ConfigDict(extra="ignore")


class MenuCategoriesResponse(BaseModel):
    """Response model for menu categories."""

    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation result")
    categories: Dict[str, List[str]] = Field(
        ..., description="Dictionary with categories as keys and arrays of sub-categories as values"
    )
