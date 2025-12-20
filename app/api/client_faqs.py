from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel, ConfigDict

from app.api.faqs import FAQBulkCreateRequest, FAQCreateRequest, FAQUpdateRequest
from app.middleware.auth_middleware import get_current_restaurant_user
from app.models.common_models import PaginationResponse
from app.services.faq_service import FAQService
from app.utils.payload_validator import validate_payload


def _validate_payload(model, payload: dict):
    return validate_payload(model, payload)


def get_faq_service() -> FAQService:
    return FAQService()


router = APIRouter(
    prefix="/api/v1/client",
    tags=["FAQs"],
    dependencies=[Depends(get_current_restaurant_user)],
)

FAQ_CREATE_SCHEMA = FAQCreateRequest.model_json_schema()
FAQ_UPDATE_SCHEMA = FAQUpdateRequest.model_json_schema()
FAQ_BULK_SCHEMA = FAQBulkCreateRequest.model_json_schema()


class ClientFAQResponse(BaseModel):
    id: int
    restaurant_id: int
    restaurant_name: str | None = None
    question: str
    answer: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(extra="ignore")


class ClientFAQListResponse(BaseModel):
    items: list[ClientFAQResponse]
    pagination: PaginationResponse
    model_config = ConfigDict(extra="ignore")


@router.post(
    "/faqs",
    status_code=status.HTTP_201_CREATED,
    summary="Create FAQ (Client)",
    description="Create a new FAQ for the authenticated restaurant user.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": FAQ_CREATE_SCHEMA,
                    "example": {"question": "Do you offer delivery?", "answer": "Yes, within 5 miles."},
                }
            },
        },
        "responses": {
            201: {
                "description": "FAQ created",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
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
    response_model=ClientFAQResponse,
    response_description="Created FAQ for the restaurant.",
)
async def create_faq(
    payload: dict | None = Body(None, description="FAQ payload with question and answer"),
    faq_service: FAQService = Depends(get_faq_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(FAQCreateRequest, payload).model_dump()
    return faq_service.create_faq(restaurant_id, data)


@router.get(
    "/faqs",
    summary="List FAQs (Client)",
    description="List FAQs for the authenticated restaurant with pagination and optional search.",
    response_model=ClientFAQListResponse,
    response_description="Paginated FAQs for the restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "FAQs retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 1,
                                    "restaurant_id": 10,
                                    "restaurant_name": "Ressy Test Kitchen",
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
async def list_faqs(
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    search: str | None = Query(None, description="Optional FULLTEXT search across question and answer"),
    faq_service: FAQService = Depends(get_faq_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    return faq_service.list_faqs_paginated(restaurant_id, page, limit, search)


@router.get(
    "/faqs/{faq_id}",
    summary="Get FAQ by ID (Client)",
    response_model=ClientFAQResponse,
    response_description="Single FAQ for the restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "FAQ retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 2,
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
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
async def get_faq(
    faq_id: int,
    faq_service: FAQService = Depends(get_faq_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    return faq_service.get_faq_for_restaurant(restaurant_id, faq_id)


@router.put(
    "/faqs/{faq_id}",
    summary="Update FAQ (Client)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": FAQ_UPDATE_SCHEMA,
                    "example": {"question": "Updated question?", "answer": "Updated answer."},
                }
            },
        },
        "responses": {
            200: {
                "description": "FAQ updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 2,
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
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
async def update_faq(
    faq_id: int,
    payload: dict | None = Body(None, description="FAQ payload with question and/or answer"),
    faq_service: FAQService = Depends(get_faq_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(FAQUpdateRequest, payload).model_dump(exclude_unset=True)
    return faq_service.update_faq_for_restaurant(restaurant_id, faq_id, data)


@router.delete(
    "/faqs/{faq_id}",
    summary="Delete FAQ (Client)",
    openapi_extra={
        "responses": {
            200: {
                "description": "FAQ deleted",
                "content": {"application/json": {"example": {"message": "FAQ deleted"}}},
            }
        }
    },
)
async def delete_faq(
    faq_id: int,
    faq_service: FAQService = Depends(get_faq_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    return faq_service.delete_faq_for_restaurant(restaurant_id, faq_id)


@router.post(
    "/faqs/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create FAQs (Client)",
    description="Bulk create FAQs for the authenticated restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": FAQ_BULK_SCHEMA,
                    "example": {
                        "faqs": [
                            {"question": "What are your hours?", "answer": "Mon-Fri 9am-9pm"},
                            {"question": "Do you take reservations?", "answer": "Yes, via phone or online"},
                        ]
                    },
                }
            },
        },
        "responses": {
            201: {
                "description": "FAQs created",
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
async def bulk_create_faqs(
    payload: dict | None = Body(None, description="Payload containing an array of FAQ objects"),
    faq_service: FAQService = Depends(get_faq_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(FAQBulkCreateRequest, payload)
    created = faq_service.bulk_create_faqs(restaurant_id, [faq.model_dump() for faq in data.faqs])
    return {"items": created}
