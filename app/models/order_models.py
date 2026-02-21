"""
Order item customization models and validation responses.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

IssueCode = Literal[
    "MISSING_REQUIRED_GROUP",
    "INVALID_OPTION",
    "EXCEEDED_MAX_SELECT",
    "BELOW_MIN_SELECT",
    "UNAVAILABLE_GROUP",
    "UNAVAILABLE_OPTION",
    "QUANTITY_NOT_ALLOWED",
    "EXCEEDED_MAX_QUANTITY_PER_OPTION",
]


class OrderOptionSelection(BaseModel):
    value_id: int
    quantity: int = Field(1, ge=1)

    model_config = ConfigDict(extra="ignore")


class OrderItemOptionGroupSelection(BaseModel):
    group_id: int
    selections: List[OrderOptionSelection]

    @field_validator("selections", mode="before")
    @classmethod
    def normalize_selections(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        normalized = []
        for selection in value:
            if isinstance(selection, int):
                normalized.append({"value_id": selection, "quantity": 1})
            else:
                normalized.append(selection)
        return normalized

    model_config = ConfigDict(extra="ignore")


class OptionValidationIssue(BaseModel):
    issue_code: IssueCode
    message: str
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    value_id: Optional[int] = None
    value_name: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class OptionValidationResult(BaseModel):
    is_valid: bool
    issues: List[OptionValidationIssue] = Field(default_factory=list)
    normalized_options: List[OrderItemOptionGroupSelection] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class OrderItemOptionSnapshot(BaseModel):
    option_value_id: Optional[int] = None
    option_group_name: str
    option_value_name: str
    price_delta: float
    quantity: int

    model_config = ConfigDict(extra="ignore")


class OrderItemSnapshot(BaseModel):
    order_item_id: int
    menu_item_id: Optional[int] = None
    item_name: str
    base_price: float
    quantity: int
    instructions: Optional[str] = None
    final_unit_price: float
    option_total: float
    total_price: float
    options: List[OrderItemOptionSnapshot] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")
