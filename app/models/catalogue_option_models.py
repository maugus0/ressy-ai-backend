"""
Catalogue option models for request/response handling.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CatalogueOptionValueCreate(BaseModel):
    """Request model for creating an option value."""

    name: str = Field(..., max_length=100, description="Name of the option value")
    price_modifier: Optional[float] = Field(None, description="Price modifier for this value")
    ordinal: Optional[int] = Field(None, description="Display order (lower numbers appear first)")

    model_config = ConfigDict(extra="ignore")


class CatalogueOptionValueUpdate(BaseModel):
    """Request model for updating an option value (all fields optional)."""

    name: Optional[str] = Field(None, max_length=100, description="Name of the option value")
    price_modifier: Optional[float] = Field(None, description="Price modifier for this value")
    ordinal: Optional[int] = Field(None, description="Display order (lower numbers appear first)")

    model_config = ConfigDict(extra="ignore")


class CatalogueOptionValueResponse(BaseModel):
    """Response model for an option value."""

    id: int = Field(..., description="Unique identifier for the option value")
    option_group_id: int = Field(..., description="ID of the option group this value belongs to")
    name: str = Field(..., description="Name of the option value")
    price_modifier: Optional[float] = Field(None, description="Price modifier for this value")
    ordinal: Optional[int] = Field(None, description="Display order")

    model_config = ConfigDict(from_attributes=True)


class CatalogueOptionGroupCreate(BaseModel):
    """Request model for creating an option group."""

    name: str = Field(..., max_length=100, description="Name of the option group")
    is_required: Optional[bool] = Field(False, description="Whether this option group is required")
    min_selections: Optional[int] = Field(0, ge=0, description="Minimum number of selections required")
    max_selections: Optional[int] = Field(None, ge=0, description="Maximum number of selections allowed (None = unlimited)")
    ordinal: Optional[int] = Field(None, description="Display order (lower numbers appear first)")
    values: Optional[List[CatalogueOptionValueCreate]] = Field(None, description="List of option values for this group")

    model_config = ConfigDict(extra="ignore")


class CatalogueOptionGroupUpdate(BaseModel):
    """Request model for updating an option group (all fields optional)."""

    name: Optional[str] = Field(None, max_length=100, description="Name of the option group")
    is_required: Optional[bool] = Field(None, description="Whether this option group is required")
    min_selections: Optional[int] = Field(None, ge=0, description="Minimum number of selections required")
    max_selections: Optional[int] = Field(None, ge=0, description="Maximum number of selections allowed (None = unlimited)")
    ordinal: Optional[int] = Field(None, description="Display order")

    model_config = ConfigDict(extra="ignore")


class CatalogueOptionGroupResponse(BaseModel):
    """Response model for an option group."""

    id: int = Field(..., description="Unique identifier for the option group")
    business_id: int = Field(..., description="ID of the business this option group belongs to")
    name: str = Field(..., description="Name of the option group")
    is_required: bool = Field(..., description="Whether this option group is required")
    min_selections: int = Field(..., description="Minimum number of selections required")
    max_selections: Optional[int] = Field(None, description="Maximum number of selections allowed")
    ordinal: Optional[int] = Field(None, description="Display order")
    values: Optional[List[CatalogueOptionValueResponse]] = Field(None, description="List of option values for this group")

    model_config = ConfigDict(from_attributes=True)


class CatalogueItemOptionGroupAttach(BaseModel):
    """Request model for attaching an option group to a catalogue item."""

    group_id: int = Field(..., description="ID of the option group to attach")
    min_select_override: Optional[int] = Field(None, ge=0, description="Override minimum selections for this item")
    max_select_override: Optional[int] = Field(None, ge=0, description="Override maximum selections for this item")
    is_required_override: Optional[bool] = Field(None, description="Override required status for this item")
    ordinal: Optional[int] = Field(None, description="Display order for this item")

    model_config = ConfigDict(extra="ignore")


class CatalogueItemOptionGroupResponse(BaseModel):
    """Response model for an option group attached to a catalogue item."""

    catalogue_item_id: int = Field(..., description="ID of the catalogue item")
    group_id: int = Field(..., description="ID of the option group")
    min_select_override: Optional[int] = Field(None, description="Override minimum selections")
    max_select_override: Optional[int] = Field(None, description="Override maximum selections")
    is_required_override: Optional[bool] = Field(None, description="Override required status")
    ordinal: Optional[int] = Field(None, description="Display order")

    model_config = ConfigDict(from_attributes=True)
