from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, field_validator, model_validator

from app.middleware.auth_middleware import get_current_admin_user
from app.services.faq_service import FAQService


def _require_non_empty(value: str | None, field_name: str) -> str:
    """Ensure a string field is present and not just whitespace."""
    if value is None:
        raise ValueError(f"{field_name} cannot be empty")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")
    return cleaned


class FAQCreateRequest(BaseModel):
    question: str
    answer: str
    model_config = ConfigDict(extra="ignore")

    @field_validator("question", "answer")
    def not_empty(cls, value: str, info: ValidationInfo):
        return _require_non_empty(value, info.field_name)


class FAQUpdateRequest(BaseModel):
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


class FAQBulkCreateRequest(BaseModel):
    faqs: list[FAQCreateRequest]
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def non_empty(self):
        if not self.faqs:
            raise ValueError("faqs list cannot be empty")
        return self


def _parse_payload(model, payload: dict):
    return model.model_validate(payload)


def _validate_payload(model, payload: dict):
    try:
        return _parse_payload(model, payload or {})
    except ValidationError as exc:
        serialized_errors = []
        for err in exc.errors():
            ctx = err.get("ctx") or {}
            ctx_serialized = {k: str(v) for k, v in ctx.items()} if ctx else None
            err_copy = {k: v for k, v in err.items() if k != "ctx"}
            if ctx_serialized:
                err_copy["ctx"] = ctx_serialized
            serialized_errors.append(err_copy)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=serialized_errors)


def get_faq_service() -> FAQService:
    return FAQService()


router = APIRouter(prefix="/api/v1/admin", tags=["FAQs"], dependencies=[Depends(get_current_admin_user)])
FAQ_CREATE_SCHEMA = FAQCreateRequest.model_json_schema()
FAQ_UPDATE_SCHEMA = FAQUpdateRequest.model_json_schema()
FAQ_BULK_SCHEMA = FAQBulkCreateRequest.model_json_schema()


@router.post(
    "/restaurants/{restaurant_id}/faqs",
    status_code=status.HTTP_201_CREATED,
    summary="Create FAQ",
    description="Create a new FAQ for the specified restaurant. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": FAQ_CREATE_SCHEMA,
                    "example": {"question": "Do you offer delivery?", "answer": "Yes, within 5 miles."},
                }
            },
        }
    },
)
async def create_faq(
    restaurant_id: int,
    payload: dict | None = Body(None, description="FAQ payload with question and answer"),
    faq_service: FAQService = Depends(get_faq_service),
):
    data = _validate_payload(FAQCreateRequest, payload or {}).model_dump()
    return faq_service.create_faq(restaurant_id, data)


@router.get(
    "/restaurants/{restaurant_id}/faqs",
    summary="List FAQs for a restaurant",
    description="Get paginated FAQs for a restaurant with optional FULLTEXT search. Admin access only.",
)
async def list_faqs(
    restaurant_id: int,
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    search: str | None = Query(None, description="Optional FULLTEXT search across question and answer"),
    faq_service: FAQService = Depends(get_faq_service),
):
    return faq_service.list_faqs_paginated(restaurant_id, page, limit, search)


@router.get(
    "/faqs/search",
    summary="Search FAQs",
    description="Search FAQs across all restaurants using FULLTEXT. Admin access only.",
)
async def search_faqs(
    q: str | None = Query(None, description="Search term for FULLTEXT search"),
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    faq_service: FAQService = Depends(get_faq_service),
):
    return faq_service.search_all(q, page, limit)


@router.get(
    "/faqs/{faq_id}",
    summary="Get FAQ by ID",
    description="Fetch a single FAQ by ID including its restaurant name. Admin access only.",
)
async def get_faq(
    faq_id: int,
    faq_service: FAQService = Depends(get_faq_service),
):
    return faq_service.get_faq(faq_id)


@router.put(
    "/faqs/{faq_id}",
    summary="Update FAQ",
    description="Update question and/or answer for a FAQ. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": FAQ_UPDATE_SCHEMA,
                    "example": {"question": "Updated question?", "answer": "Updated answer."},
                }
            },
        }
    },
)
async def update_faq(
    faq_id: int,
    payload: dict | None = Body(None, description="FAQ payload with question and/or answer"),
    faq_service: FAQService = Depends(get_faq_service),
):
    data = _validate_payload(FAQUpdateRequest, payload or {}).model_dump(exclude_unset=True)
    return faq_service.update_faq(faq_id, data)


@router.delete(
    "/faqs/{faq_id}",
    summary="Delete FAQ",
    description="Delete a FAQ by ID. Admin access only.",
)
async def delete_faq(
    faq_id: int,
    faq_service: FAQService = Depends(get_faq_service),
):
    return faq_service.delete_faq(faq_id)


@router.post(
    "/restaurants/{restaurant_id}/faqs/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create FAQs",
    description="Bulk create FAQs for a restaurant in a single transaction. Admin access only.",
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
        }
    },
)
async def bulk_create_faqs(
    restaurant_id: int,
    payload: dict | None = Body(None, description="Payload containing an array of FAQ objects"),
    faq_service: FAQService = Depends(get_faq_service),
):
    data = _validate_payload(FAQBulkCreateRequest, payload or {})
    created = faq_service.bulk_create_faqs(restaurant_id, [faq.model_dump() for faq in data.faqs])
    return {"items": created}
