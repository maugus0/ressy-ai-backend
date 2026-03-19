from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.middleware.auth_middleware import get_current_admin_user
from app.models.escalation_models import (
    EscalationDetailResponse,
    EscalationListItem,
    EscalationListPage,
    EscalationStatusUpdateRequest,
)
from app.services.business_escalation_service import BusinessEscalationService
from app.utils.escalation_utils import normalize_escalation
from app.utils.payload_validator import validate_payload


def get_escalation_service() -> BusinessEscalationService:
    return BusinessEscalationService()


router = APIRouter(
    prefix="/api/v2/admin",
    tags=["Business_Escalations"],
    dependencies=[Depends(get_current_admin_user)],
)

STATUS_UPDATE_SCHEMA = EscalationStatusUpdateRequest.model_json_schema()


@router.get(
    "/escalations",
    summary="Get all escalations (Admin)",
    description="Retrieve paginated escalations across all businesss with filtering, sorting, and pagination.",
    response_model=EscalationListPage,
    response_description="Paginated escalations with business metadata.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Business_Escalations retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 7,
                                    "call_id": "123",
                                    "user_id": "456",
                                    "business_id": "10",
                                    "business_name": "Ressy Test Kitchen",
                                    "call_sid": "CA123",
                                    "caller_phone": "+14155551234",
                                    "escalation_phone_number": "+15550001111",
                                    "urgency": "high",
                                    "reason": "customer asked for a manager",
                                    "status": "raised",
                                    "requested_at": "2024-03-01T12:00:00Z",
                                }
                            ],
                            "total": 1,
                            "page": 1,
                            "limit": 20,
                        }
                    }
                },
            }
        }
    },
)
async def get_admin_escalations(
    business_id: str | None = Query(
        None,
        description="Filter by business id",
        examples={"sample": {"summary": "Restaurant ID", "value": "10"}},
    ),
    status: str | None = Query(
        None, description="Escalation status filter", examples={"sample": {"summary": "Status", "value": "raised"}}
    ),
    urgency: str | None = Query(
        None, description="Urgency filter", examples={"sample": {"summary": "Urgency", "value": "high"}}
    ),
    reason: str | None = Query(
        None,
        description="Reason filter (partial match)",
        examples={"sample": {"summary": "Reason", "value": "manager"}},
    ),
    caller_phone: str | None = Query(
        None, description="Search by caller phone (partial)", examples={"sample": {"summary": "Phone", "value": "+141"}}
    ),
    call_id: str | None = Query(
        None, description="Filter by internal call ID", examples={"sample": {"summary": "Call ID", "value": "123"}}
    ),
    call_sid: str | None = Query(
        None, description="Filter by Twilio call SID", examples={"sample": {"summary": "Call SID", "value": "CA123"}}
    ),
    date_from: str | None = Query(
        None,
        description="Start date (ISO 8601, e.g. 2024-03-01T00:00:00Z)",
        examples={"sample": {"summary": "Example start", "value": "2024-03-01T00:00:00Z"}},
    ),
    date_to: str | None = Query(
        None,
        description="End date (ISO 8601, e.g. 2024-03-31T23:59:59Z)",
        examples={"sample": {"summary": "Example end", "value": "2024-03-31T23:59:59Z"}},
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=200, description="Items per page"),
    sort_by: str = Query("requested_at", description="requested_at, created_at, updated_at, status"),
    sort_order: str = Query("desc", description="Sort order asc/desc"),
    escalation_service: BusinessEscalationService = Depends(get_escalation_service),
):
    rows, total = escalation_service.list_escalations(
        business_id=business_id,
        status=status,
        urgency=urgency,
        reason=reason,
        caller_phone=caller_phone,
        call_id=call_id,
        call_sid=call_sid,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items = [EscalationListItem(**normalize_escalation(row)) for row in rows]
    return EscalationListPage(items=items, total=total, page=page, limit=limit)


@router.get(
    "/escalations/{escalation_id}",
    summary="Get escalation detail (Admin)",
    description="Retrieve details for a specific escalation. Admin access only.",
    response_model=EscalationDetailResponse,
    response_description="Escalation detail with metadata.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Escalation detail",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 7,
                            "call_id": "123",
                            "user_id": "456",
                            "business_id": "10",
                            "business_name": "Ressy Test Kitchen",
                            "call_sid": "CA123",
                            "caller_phone": "+14155551234",
                            "escalation_phone_number": "+15550001111",
                            "urgency": "high",
                            "reason": "customer asked for a manager",
                            "status": "raised",
                            "requested_at": "2024-03-01T12:00:00Z",
                            "forwarded_at": None,
                            "created_at": "2024-03-01T12:00:00Z",
                            "updated_at": "2024-03-01T12:00:00Z",
                        }
                    }
                },
            }
        }
    },
)
async def get_admin_escalation(
    escalation_id: int, escalation_service: BusinessEscalationService = Depends(get_escalation_service)
) -> EscalationDetailResponse:
    escalation = escalation_service.get_escalation(escalation_id)
    if not escalation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
    return EscalationDetailResponse(**normalize_escalation(escalation))


@router.patch(
    "/escalations/{escalation_id}/status",
    summary="Update escalation status (Admin)",
    description="Update the status of an escalation. Allowed statuses: raised, forwarded, failed, resolved.",
    response_model=EscalationDetailResponse,
    response_description="Updated escalation details.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": STATUS_UPDATE_SCHEMA, "example": {"status": "forwarded"}}},
        },
        "responses": {
            200: {
                "description": "Escalation updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 7,
                            "call_id": "123",
                            "user_id": "456",
                            "business_id": "10",
                            "business_name": "Ressy Test Kitchen",
                            "call_sid": "CA123",
                            "caller_phone": "+14155551234",
                            "escalation_phone_number": "+15550001111",
                            "urgency": "high",
                            "reason": "customer asked for a manager",
                            "status": "forwarded",
                            "requested_at": "2024-03-01T12:00:00Z",
                            "forwarded_at": "2024-03-01T12:02:00Z",
                            "created_at": "2024-03-01T12:00:00Z",
                            "updated_at": "2024-03-01T12:02:00Z",
                        }
                    }
                },
            }
        },
    },
)
async def update_admin_escalation_status(
    escalation_id: int,
    payload: dict = Body(..., description="Escalation status update"),
    escalation_service: BusinessEscalationService = Depends(get_escalation_service),
) -> EscalationDetailResponse:
    data = validate_payload(EscalationStatusUpdateRequest, payload)
    try:
        updated = escalation_service.update_escalation_status(escalation_id, data.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
    return EscalationDetailResponse(**normalize_escalation(updated))
