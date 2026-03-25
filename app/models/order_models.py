"""
Order item customization models and validation responses.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IssueCode = Literal[
    "MISSING_REQUIRED_GROUP",
    "INVALID_OPTION",
    "EXCEEDED_MAX_SELECT",
    "BELOW_MIN_SELECT",
    "UNAVAILABLE_GROUP",
    "UNAVAILABLE_OPTION",
    "QUANTITY_NOT_ALLOWED",
    "EXCEEDED_MAX_QUANTITY_PER_OPTION",
    "MISSING_TEXT_VALUE",
    "TEXT_NOT_ALLOWED",
    "TEXT_TOO_LONG",
]


class OrderOptionSelection(BaseModel):
    value_id: Optional[int] = None
    free_text_value: Optional[str] = None
    quantity: int = Field(1, ge=1)

    @field_validator("free_text_value", mode="before")
    @classmethod
    def normalize_free_text_value(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def validate_selection(self):
        if self.value_id is not None and self.free_text_value:
            raise ValueError("Provide either value_id or free_text_value, not both.")
        return self

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
    option_group_id: Optional[int] = None
    option_value_id: Optional[int] = None
    option_group_name: str
    input_type: Optional[str] = None
    option_value_name: Optional[str] = None
    free_text_value: Optional[str] = None
    external_group_id_snapshot: Optional[str] = None
    external_value_id_snapshot: Optional[str] = None
    price_delta: float
    quantity: int

    model_config = ConfigDict(extra="ignore")


class OrderItemSnapshot(BaseModel):
    order_item_id: int
    menu_item_id: Optional[int] = None
    external_item_id_snapshot: Optional[str] = None
    item_name: str
    base_price: float
    quantity: int
    instructions: Optional[str] = None
    final_unit_price: float
    option_total: float
    total_price: float
    options: List[OrderItemOptionSnapshot] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")
