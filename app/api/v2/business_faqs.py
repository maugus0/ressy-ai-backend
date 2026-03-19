from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from app.middleware.auth_middleware import get_current_admin_user
from app.models.common_models import PaginationResponse
from app.services.business_faq_service import BusinessFAQService
from app.utils.payload_validator import validate_payload


def _require_non_empty(value: str | None, field_name: str) -> str:
    """Ensure a string field is present and not just whitespace."""
    if value is None:
        raise ValueError(f"{field_name} cannot be empty")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")
    return cleaned


class BusinessFAQCreateRequest(BaseModel):
    question: str
    answer: str
    model_config = ConfigDict(extra="ignore")

    @field_validator("question", "answer")
    def not_empty(cls, value: str, info: ValidationInfo):
        return _require_non_empty(value, info.field_name)


class BusinessFAQUpdateRequest(BaseModel):
    question: str | None = None
    answer: str | None = None
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.question is None and self.answer is None:
            raise ValueError("At least one of question or answer must be provided")
        if self.question is not None:
            self.question = _require_non_empty(self.question, "question")
        if self.answer is not None:
            self.answer = _require_non_empty(self.answer, "answer")
        return self


class BusinessFAQBulkCreateRequest(BaseModel):
    business_faqs: list[BusinessFAQCreateRequest]
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def non_empty(self):
        if not self.business_faqs:
            raise ValueError("business_faqs list cannot be empty")
        return self


def _validate_payload(model, payload: dict):
    return validate_payload(model, payload)


def get_business_faq_service() -> BusinessFAQService:
    return BusinessFAQService()


router = APIRouter(prefix="/api/v2/admin", tags=["Business_BusinessFAQs"], dependencies=[Depends(get_current_admin_user)])
BusinessFAQ_CREATE_SCHEMA = BusinessFAQCreateRequest.model_json_schema()
BusinessFAQ_UPDATE_SCHEMA = BusinessFAQUpdateRequest.model_json_schema()
BusinessFAQ_BULK_SCHEMA = BusinessFAQBulkCreateRequest.model_json_schema()


class BusinessFAQResponse(BaseModel):
    id: int
    business_id: int
    business_name: str | None = None
    question: str
    answer: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(extra="ignore")


class BusinessFAQListResponse(BaseModel):
    items: list[BusinessFAQResponse]
    pagination: PaginationResponse
    model_config = ConfigDict(extra="ignore")


@router.post(
    "/businesss/{business_id}/business_faqs",
    status_code=status.HTTP_201_CREATED,
    summary="Create BusinessFAQ",
    description="Create a new BusinessFAQ for the specified business. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BusinessFAQ_CREATE_SCHEMA,
                    "example": {"question": "Do you offer delivery?", "answer": "Yes, within 5 miles."},
                }
            },
        }
    },
)
async def create_business_faq(
    business_id: int,
    payload: dict | None = Body(None, description="BusinessFAQ payload with question and answer"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
):
    data = _validate_payload(BusinessFAQCreateRequest, payload).model_dump()
    return business_faq_service.create_business_faq(business_id, data)


@router.get(
    "/businesss/{business_id}/business_faqs",
    summary="List Business_BusinessFAQs for a business",
    description="Get paginated Business_BusinessFAQs for a business with optional FULLTEXT search. Admin access only.",
    response_model=BusinessFAQListResponse,
    response_description="Paginated list of Business_BusinessFAQs with metadata.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Business_BusinessFAQs retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 1,
                                    "business_id": 10,
                                    "business_name": "Ressy Test Kitchen",
                                    "question": "Do you offer delivery?",
                                    "answer": "Yes, within 5 miles.",
                                    "created_at": "2024-02-01T10:00:00Z",
                                    "updated_at": "2024-02-01T10:00:00Z",
                                }
                            ],
                            "pagination": {"page": 1, "limit": 20, "total": 1, "pages": 1},
                        }
                    }
                },
            }
        }
    },
)
async def list_business_faqs(
    business_id: int,
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    search: str | None = Query(None, description="Optional FULLTEXT search across question and answer"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
):
    return business_faq_service.list_business_faqs_paginated(business_id, page, limit, search)


@router.get(
    "/business_faqs/search",
    summary="Search Business_BusinessFAQs",
    description="Search Business_BusinessFAQs across all businesss using FULLTEXT. Admin access only.",
    response_model=BusinessFAQListResponse,
    response_description="Paginated Business_BusinessFAQs with business names for search results.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Search results",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 5,
                                    "business_id": 12,
                                    "business_name": "Pizza Plaza",
                                    "question": "Do you have gluten-free pizza?",
                                    "answer": "Yes, we have gluten-free crust.",
                                    "created_at": "2024-02-05T12:00:00Z",
                                    "updated_at": "2024-02-05T12:00:00Z",
                                }
                            ],
                            "pagination": {"page": 1, "limit": 20, "total": 1, "pages": 1},
                        }
                    }
                },
            }
        }
    },
)
async def search_business_faqs(
    q: str | None = Query(None, description="Search term for FULLTEXT search"),
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
):
    return business_faq_service.search_all(q, page, limit)


@router.get(
    "/business_faqs/{business_faq_id}",
    summary="Get BusinessFAQ by ID",
    description="Fetch a single BusinessFAQ by ID including its business name. Admin access only.",
    response_model=BusinessFAQResponse,
    response_description="Single BusinessFAQ record.",
    openapi_extra={
        "responses": {
            200: {
                "description": "BusinessFAQ retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 2,
                            "business_id": 10,
                            "business_name": "Ressy Test Kitchen",
                            "question": "Do you take reservations?",
                            "answer": "Yes, via phone or online.",
                            "created_at": "2024-02-02T10:00:00Z",
                            "updated_at": "2024-02-03T09:30:00Z",
                        }
                    }
                },
            }
        }
    },
)
async def get_business_faq(
    business_faq_id: int,
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
):
    return business_faq_service.get_business_faq(business_faq_id)


@router.put(
    "/business_faqs/{business_faq_id}",
    summary="Update BusinessFAQ",
    description="Update question and/or answer for a BusinessFAQ. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BusinessFAQ_UPDATE_SCHEMA,
                    "example": {"question": "Updated question?", "answer": "Updated answer."},
                }
            },
        }
    },
)
async def update_business_faq(
    business_faq_id: int,
    payload: dict | None = Body(None, description="BusinessFAQ payload with question and/or answer"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
):
    data = _validate_payload(BusinessFAQUpdateRequest, payload).model_dump(exclude_unset=True)
    return business_faq_service.update_business_faq(business_faq_id, data)


@router.delete(
    "/business_faqs/{business_faq_id}",
    summary="Delete BusinessFAQ",
    description="Delete a BusinessFAQ by ID. Admin access only.",
)
async def delete_business_faq(
    business_faq_id: int,
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
):
    return business_faq_service.delete_business_faq(business_faq_id)


@router.post(
    "/businesss/{business_id}/business_faqs/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create Business_BusinessFAQs",
    description="Bulk create Business_BusinessFAQs for a business in a single transaction. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BusinessFAQ_BULK_SCHEMA,
                    "example": {
                        "business_faqs": [
                            {"question": "What are your hours?", "answer": "Mon-Fri 9am-9pm"},
                            {"question": "Do you take reservations?", "answer": "Yes, via phone or online"},
                        ]
                    },
                }
            },
        }
    },
)
async def bulk_create_business_faqs(
    business_id: int,
    payload: dict | None = Body(None, description="Payload containing an array of BusinessFAQ objects"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
):
    data = _validate_payload(BusinessFAQBulkCreateRequest, payload)
    created = business_faq_service.bulk_create_business_faqs(business_id, [business_faq.model_dump() for business_faq in data.business_faqs])
    return {"items": created}
