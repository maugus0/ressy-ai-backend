from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel, ConfigDict

from app.api.v2.business_faqs import BusinessFAQBulkCreateRequest, BusinessFAQCreateRequest, BusinessFAQUpdateRequest
from app.middleware.auth_middleware import get_current_business_user
from app.models.common_models import PaginationResponse
from app.services.business_faq_service import BusinessFAQService
from app.utils.payload_validator import validate_payload


def _validate_payload(model, payload: dict):
    return validate_payload(model, payload)


def get_business_faq_service() -> BusinessFAQService:
    return BusinessFAQService()


router = APIRouter(
    prefix="/api/v2/client",
    tags=["Business_BusinessFAQs"],
    dependencies=[Depends(get_current_business_user)],
)

BusinessFAQ_CREATE_SCHEMA = BusinessFAQCreateRequest.model_json_schema()
BusinessFAQ_UPDATE_SCHEMA = BusinessFAQUpdateRequest.model_json_schema()
BusinessFAQ_BULK_SCHEMA = BusinessFAQBulkCreateRequest.model_json_schema()


class ClientBusinessFAQResponse(BaseModel):
    id: int
    business_id: int
    business_name: str | None = None
    question: str
    answer: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(extra="ignore")


class ClientBusinessFAQListResponse(BaseModel):
    items: list[ClientBusinessFAQResponse]
    pagination: PaginationResponse
    model_config = ConfigDict(extra="ignore")


@router.post(
    "/business_faqs",
    status_code=status.HTTP_201_CREATED,
    summary="Create BusinessFAQ (Client)",
    description="Create a new BusinessFAQ for the authenticated business user.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BusinessFAQ_CREATE_SCHEMA,
                    "example": {"question": "Do you offer delivery?", "answer": "Yes, within 5 miles."},
                }
            },
        },
        "responses": {
            201: {
                "description": "BusinessFAQ created",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "business_id": 10,
                            "business_name": "Ressy Test Kitchen",
                            "question": "Do you offer delivery?",
                            "answer": "Yes, within 5 miles.",
                            "created_at": "2024-02-01T10:00:00Z",
                            "updated_at": "2024-02-01T10:00:00Z",
                        }
                    }
                },
            }
        },
    },
    response_model=ClientBusinessFAQResponse,
    response_description="Created BusinessFAQ for the business.",
)
async def create_business_faq(
    payload: dict | None = Body(None, description="BusinessFAQ payload with question and answer"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
    claims: dict = Depends(get_current_business_user),
):
    business_id = int(claims["business_id"])
    data = _validate_payload(BusinessFAQCreateRequest, payload).model_dump()
    return business_faq_service.create_business_faq(business_id, data)


@router.get(
    "/business_faqs",
    summary="List Business_BusinessFAQs (Client)",
    description="List Business_BusinessFAQs for the authenticated business with pagination and optional search.",
    response_model=ClientBusinessFAQListResponse,
    response_description="Paginated Business_BusinessFAQs for the business.",
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
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    search: str | None = Query(None, description="Optional FULLTEXT search across question and answer"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
    claims: dict = Depends(get_current_business_user),
):
    business_id = int(claims["business_id"])
    return business_faq_service.list_business_faqs_paginated(business_id, page, limit, search)


@router.get(
    "/business_faqs/{business_faq_id}",
    summary="Get BusinessFAQ by ID (Client)",
    response_model=ClientBusinessFAQResponse,
    response_description="Single BusinessFAQ for the business.",
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
    claims: dict = Depends(get_current_business_user),
):
    business_id = int(claims["business_id"])
    return business_faq_service.get_business_faq_for_business(business_id, business_faq_id)


@router.put(
    "/business_faqs/{business_faq_id}",
    summary="Update BusinessFAQ (Client)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BusinessFAQ_UPDATE_SCHEMA,
                    "example": {"question": "Updated question?", "answer": "Updated answer."},
                }
            },
        },
        "responses": {
            200: {
                "description": "BusinessFAQ updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 2,
                            "business_id": 10,
                            "business_name": "Ressy Test Kitchen",
                            "question": "Do you take reservations?",
                            "answer": "Updated answer.",
                            "created_at": "2024-02-02T10:00:00Z",
                            "updated_at": "2024-02-03T09:30:00Z",
                        }
                    }
                },
            }
        },
    },
)
async def update_business_faq(
    business_faq_id: int,
    payload: dict | None = Body(None, description="BusinessFAQ payload with question and/or answer"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
    claims: dict = Depends(get_current_business_user),
):
    business_id = int(claims["business_id"])
    data = _validate_payload(BusinessFAQUpdateRequest, payload).model_dump(exclude_unset=True)
    return business_faq_service.update_business_faq_for_business(business_id, business_faq_id, data)


@router.delete(
    "/business_faqs/{business_faq_id}",
    summary="Delete BusinessFAQ (Client)",
    openapi_extra={
        "responses": {
            200: {
                "description": "BusinessFAQ deleted",
                "content": {"application/json": {"example": {"message": "BusinessFAQ deleted"}}},
            }
        }
    },
)
async def delete_business_faq(
    business_faq_id: int,
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
    claims: dict = Depends(get_current_business_user),
):
    business_id = int(claims["business_id"])
    return business_faq_service.delete_business_faq_for_business(business_id, business_faq_id)


@router.post(
    "/business_faqs/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create Business_BusinessFAQs (Client)",
    description="Bulk create Business_BusinessFAQs for the authenticated business.",
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
        },
        "responses": {
            201: {
                "description": "Business_BusinessFAQs created",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {"id": 1, "question": "What are your hours?", "answer": "Mon-Fri 9am-9pm"},
                                {"id": 2, "question": "Do you take reservations?", "answer": "Yes"},
                            ]
                        }
                    }
                },
            }
        },
    },
)
async def bulk_create_business_faqs(
    payload: dict | None = Body(None, description="Payload containing an array of BusinessFAQ objects"),
    business_faq_service: BusinessFAQService = Depends(get_business_faq_service),
    claims: dict = Depends(get_current_business_user),
):
    business_id = int(claims["business_id"])
    data = _validate_payload(BusinessFAQBulkCreateRequest, payload)
    created = business_faq_service.bulk_create_business_faqs(business_id, [business_faq.model_dump() for business_faq in data.business_faqs])
    return {"items": created}
