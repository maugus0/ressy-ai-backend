"""
Shared provider-agnostic POS integration models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class POSCatalogIssue:
    scope: str
    issue_type: str
    title: str
    severity: str = "ERROR"
    external_object_id: Optional[str] = None
    external_parent_id: Optional[str] = None
    details: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogOptionValue:
    external_id: str
    name: str
    price_delta: float = 0.0
    is_default: bool = False
    is_available: bool = True
    sort_order: int = 0
    external_group_id: Optional[str] = None
    external_object_type: str = "OPTION_VALUE"
    external_version: Optional[str] = None
    source_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogOptionGroupAttachment:
    selection_type: Optional[str] = None
    min_select: Optional[int] = None
    max_select: Optional[int] = None
    free_allowance: Optional[int] = None
    allows_quantity: Optional[bool] = None
    max_quantity_per_option: Optional[int] = None
    is_required: Optional[bool] = None
    sort_order: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogOptionGroup:
    external_id: str
    name: str
    description: Optional[str] = None
    selection_type: str = "multiple"
    min_select: int = 0
    max_select: Optional[int] = None
    free_allowance: int = 0
    free_allowance_strategy: str = "HIGHEST_PRICE_FIRST"
    allows_quantity: bool = False
    max_quantity_per_option: Optional[int] = None
    prompt_style: str = "ASK_IF_MENTIONED"
    is_required: bool = False
    is_available: bool = True
    sort_order: int = 0
    input_type: str = "SELECT"
    text_required: bool = False
    max_text_length: Optional[int] = None
    values: List[POSCatalogOptionValue] = field(default_factory=list)
    external_parent_id: Optional[str] = None
    external_object_type: str = "OPTION_GROUP"
    external_version: Optional[str] = None
    source_name: Optional[str] = None
    source_description: Optional[str] = None
    attachment: POSCatalogOptionGroupAttachment = field(default_factory=POSCatalogOptionGroupAttachment)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogMenuItem:
    external_id: str
    name: str
    description: Optional[str]
    price: float
    category: Optional[str] = None
    sub_category: Optional[str] = None
    is_available: bool = True
    is_active: bool = True
    avg_prep_time: Optional[int] = None
    option_groups: List[POSCatalogOptionGroup] = field(default_factory=list)
    external_parent_id: Optional[str] = None
    external_object_type: str = "ITEM"
    external_version: Optional[str] = None
    source_name: Optional[str] = None
    source_description: Optional[str] = None
    source_category: Optional[str] = None
    source_sub_category: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogSnapshot:
    items: List[POSCatalogMenuItem]
    catalog_version: Optional[str] = None
    issues: List[POSCatalogIssue] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogAvailabilityItem:
    external_id: str
    is_available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogAvailabilityOptionValue:
    external_id: str
    external_group_id: Optional[str] = None
    is_available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSCatalogAvailabilitySnapshot:
    items: List[POSCatalogAvailabilityItem] = field(default_factory=list)
    option_values: List[POSCatalogAvailabilityOptionValue] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSOrderModifierSelection:
    external_group_id: Optional[str]
    external_value_id: Optional[str]
    name: str
    quantity: int = 1
    price_delta: float = 0.0
    free_text_value: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSOrderLineItem:
    external_item_id: str
    name: str
    quantity: int
    price: float
    discount_amount: float = 0.0
    note: Optional[str] = None
    modifiers: List[POSOrderModifierSelection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSSubmitOrderRequest:
    restaurant_id: int
    location_id: str
    currency: str
    reference_id: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    pickup_at: Optional[str] = None
    line_items: List[POSOrderLineItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class POSOrderSubmissionResult:
    external_order_id: Optional[str]
    status: str
    payload: Dict[str, Any]
    external_payment_id: Optional[str] = None


@dataclass(frozen=True)
class POSOrderCancellationResult:
    external_order_id: Optional[str]
    status: str
    payload: Dict[str, Any]
    external_payment_id: Optional[str] = None
