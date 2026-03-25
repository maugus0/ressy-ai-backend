"""
Menu option group/value models for customization management.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SelectionType = Literal["single", "multiple"]
PromptStyle = Literal["ASK_ALWAYS", "ASK_IF_MENTIONED", "SUGGEST_POPULAR"]
FreeAllowanceStrategy = Literal["HIGHEST_PRICE_FIRST", "LOWEST_PRICE_FIRST"]
InputType = Literal["SELECT", "TEXT"]


class MenuOptionValueCreate(BaseModel):
    name: str = Field(..., max_length=150)
    price_delta: float = Field(0, ge=0)
    is_default: bool = Field(False)
    is_available: bool = Field(True)
    sort_order: int = Field(0, ge=0)

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"example": {"name": "Extra Cheese", "price_delta": 1.25, "is_default": False}},
    )


class MenuOptionValueUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    price_delta: Optional[float] = Field(None, ge=0)
    is_default: Optional[bool] = Field(None)
    is_available: Optional[bool] = Field(None)
    sort_order: Optional[int] = Field(None, ge=0)

    model_config = ConfigDict(extra="ignore", json_schema_extra={"example": {"is_available": False}})


class MenuOptionValueResponse(BaseModel):
    id: int
    group_id: int
    name: str
    price_delta: float
    is_default: bool
    is_available: bool
    sort_order: int
    is_active: bool = True
    catalog_source: str = "INTERNAL"
    source_name: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 101,
                "group_id": 12,
                "name": "Pepperoni",
                "price_delta": 1.5,
                "is_default": False,
                "is_available": True,
                "sort_order": 1,
            }
        },
    )


class MenuOptionGroupCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: Optional[str] = None
    selection_type: SelectionType = Field("multiple")
    input_type: InputType = Field("SELECT")
    min_select: int = Field(0, ge=0)
    max_select: Optional[int] = Field(None, ge=0)
    free_allowance: int = Field(0, ge=0)
    free_allowance_strategy: FreeAllowanceStrategy = Field("HIGHEST_PRICE_FIRST")
    allows_quantity: bool = Field(False)
    max_quantity_per_option: Optional[int] = Field(None, ge=1)
    prompt_style: PromptStyle = Field("ASK_IF_MENTIONED")
    is_required: bool = Field(False)
    is_available: bool = Field(True)
    is_active: bool = Field(True)
    catalog_source: str = Field("INTERNAL")
    source_name: Optional[str] = None
    source_description: Optional[str] = None
    text_required: bool = Field(False)
    max_text_length: Optional[int] = Field(None, ge=1)
    sort_order: int = Field(0, ge=0)
    values: Optional[List[MenuOptionValueCreate]] = None

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "name": "Toppings",
                "description": "Choose your toppings",
                "selection_type": "multiple",
                "input_type": "SELECT",
                "min_select": 0,
                "max_select": 5,
                "free_allowance": 2,
                "free_allowance_strategy": "HIGHEST_PRICE_FIRST",
                "allows_quantity": True,
                "max_quantity_per_option": 2,
                "prompt_style": "ASK_ALWAYS",
                "is_required": False,
                "is_available": True,
                "sort_order": 1,
                "values": [
                    {"name": "Pepperoni", "price_delta": 1.5, "is_default": False, "is_available": True},
                    {"name": "Mushrooms", "price_delta": 1.0, "is_default": False, "is_available": True},
                ],
            }
        },
    )


class MenuOptionGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    description: Optional[str] = None
    selection_type: Optional[SelectionType] = None
    input_type: Optional[InputType] = None
    min_select: Optional[int] = Field(None, ge=0)
    max_select: Optional[int] = Field(None, ge=0)
    free_allowance: Optional[int] = Field(None, ge=0)
    free_allowance_strategy: Optional[FreeAllowanceStrategy] = None
    allows_quantity: Optional[bool] = None
    max_quantity_per_option: Optional[int] = Field(None, ge=1)
    prompt_style: Optional[PromptStyle] = None
    is_required: Optional[bool] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None
    catalog_source: Optional[str] = None
    source_name: Optional[str] = None
    source_description: Optional[str] = None
    text_required: Optional[bool] = None
    max_text_length: Optional[int] = Field(None, ge=1)
    sort_order: Optional[int] = Field(None, ge=0)

    model_config = ConfigDict(extra="ignore", json_schema_extra={"example": {"max_select": 4, "free_allowance": 1}})


class MenuOptionGroupResponse(BaseModel):
    id: int
    restaurant_id: int
    name: str
    description: Optional[str] = None
    selection_type: SelectionType
    input_type: InputType = Field("SELECT")
    min_select: int
    max_select: Optional[int] = None
    free_allowance: int
    free_allowance_strategy: FreeAllowanceStrategy = Field("HIGHEST_PRICE_FIRST")
    allows_quantity: bool
    max_quantity_per_option: Optional[int] = None
    prompt_style: PromptStyle
    is_required: bool
    is_available: bool
    is_active: bool = True
    catalog_source: str = "INTERNAL"
    source_name: Optional[str] = None
    source_description: Optional[str] = None
    text_required: bool = False
    max_text_length: Optional[int] = None
    sort_order: int
    values: List[MenuOptionValueResponse] = Field(default_factory=list)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12,
                "restaurant_id": 3,
                "name": "Toppings",
                "description": "Choose your toppings",
                "selection_type": "multiple",
                "input_type": "SELECT",
                "min_select": 0,
                "max_select": 5,
                "free_allowance": 2,
                "free_allowance_strategy": "HIGHEST_PRICE_FIRST",
                "allows_quantity": True,
                "max_quantity_per_option": 2,
                "prompt_style": "ASK_ALWAYS",
                "is_required": False,
                "is_available": True,
                "sort_order": 1,
                "values": [
                    {
                        "id": 101,
                        "group_id": 12,
                        "name": "Pepperoni",
                        "price_delta": 1.5,
                        "is_default": False,
                        "is_available": True,
                        "sort_order": 1,
                    }
                ],
            }
        },
    )


class MenuItemOptionGroupAttach(BaseModel):
    group_id: int
    selection_type_override: Optional[SelectionType] = None
    min_select_override: Optional[int] = Field(None, ge=0)
    max_select_override: Optional[int] = Field(None, ge=0)
    free_allowance_override: Optional[int] = Field(None, ge=0)
    allows_quantity_override: Optional[bool] = None
    max_quantity_per_option_override: Optional[int] = Field(None, ge=1)
    is_required_override: Optional[bool] = None
    sort_order: int = Field(0, ge=0)

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "group_id": 12,
                "selection_type_override": "multiple",
                "min_select_override": 0,
                "max_select_override": 3,
                "free_allowance_override": 1,
                "allows_quantity_override": True,
                "max_quantity_per_option_override": 2,
                "is_required_override": False,
                "sort_order": 1,
            }
        },
    )


class MenuItemOptionGroupResponse(BaseModel):
    menu_item_id: int
    group_id: int
    selection_type_override: Optional[SelectionType] = None
    min_select_override: Optional[int] = None
    max_select_override: Optional[int] = None
    free_allowance_override: Optional[int] = None
    allows_quantity_override: Optional[bool] = None
    max_quantity_per_option_override: Optional[int] = None
    is_required_override: Optional[bool] = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
