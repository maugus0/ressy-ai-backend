from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.middleware.auth_middleware import get_current_business_user
from app.models.call_models import CallAnalyticsV2, CallDetailResponse, CallListPage
from app.services.business_call_service import BusinessCallService


def get_call_service() -> BusinessCallService:
    return BusinessCallService()


router = APIRouter(
    prefix="/api/v2/client",
    tags=["Business_Calls"],
    dependencies=[Depends(get_current_business_user)],
)


@router.get(
    "/calls",
    summary="Get own calls (Client)",
    description="Retrieve paginated call history scoped to the authenticated business with filtering and sorting.",
    response_model=CallListPage,
    response_description="Paginated calls for the business.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Business_Calls retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "call_id": "123",
                                    "business_id": "10",
                                    "business_name": "Ressy Test Kitchen",
                                    "caller_phone": "+14155551234",
                                    "duration_seconds": 320,
                                    "status": "completed",
                                    "started_at": "2024-03-01T12:00:00Z",
                                    "has_transcript": True,
                                    "summary": "Reservation created",
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
async def get_client_calls(
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
    status: str | None = Query(
        None,
        description="Call status filter (in_progress, completed, failed, escalated, agent_bypassed)",
        examples={"sample": {"summary": "Status", "value": "agent_bypassed"}},
    ),
    duration_min: int | None = Query(
        None, ge=0, description="Minimum duration (seconds)", examples={"sample": {"summary": "Min", "value": 30}}
    ),
    duration_max: int | None = Query(
        None, ge=0, description="Maximum duration (seconds)", examples={"sample": {"summary": "Max", "value": 600}}
    ),
    caller_phone: str | None = Query(
        None,
        description="Search by caller phone (partial)",
        examples={"sample": {"summary": "Phone", "value": "+1415555"}},
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=200, description="Items per page"),
    sort_by: str = Query("created_at", description="created_at or duration"),
    sort_order: str = Query("desc", description="Sort order asc/desc"),
    claims: dict = Depends(get_current_business_user),
    call_service: BusinessCallService = Depends(get_call_service),
):
    business_id = claims.get("business_id")
    if not business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access required")
    return call_service.list_calls(
        business_id=str(business_id),
        date_from=date_from,
        date_to=date_to,
        status=status,
        duration_min=duration_min,
        duration_max=duration_max,
        caller_phone=caller_phone,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/calls/analytics",
    summary="Get call analytics (Client)",
    description="Aggregated analytics for the authenticated business within the specified date range.",
    response_model=CallAnalyticsV2,
    response_description="Analytics totals and distributions.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Analytics summary",
                "content": {
                    "application/json": {
                        "example": {
                            "total_calls": 56,
                            "average_call_duration": 198.3,
                            "status_breakdown": {"completed": 45, "failed": 5, "abandoned": 6},
                            "time_of_day_distribution": [{"hour_bucket": 18, "count": 12}],
                            "top_businesss": None,
                            "calls_by_day_of_week": [{"day_of_week": 5, "count": 14}],
                            "conversion_rates": {"orders": 0, "reservations": 0, "rate": 0},
                        }
                    }
                },
            }
        }
    },
)
async def get_client_call_analytics(
    date_from: str = Query(
        ...,
        description="Start date (ISO 8601)",
        examples={"sample": {"summary": "Example start", "value": "2024-03-01T00:00:00Z"}},
    ),
    date_to: str = Query(
        ...,
        description="End date (ISO 8601)",
        examples={"sample": {"summary": "Example end", "value": "2024-03-31T23:59:59Z"}},
    ),
    claims: dict = Depends(get_current_business_user),
    call_service: BusinessCallService = Depends(get_call_service),
):
    business_id = claims.get("business_id")
    if not business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access required")
    return call_service.get_dashboard_analytics(business_id=str(business_id), date_from=date_from, date_to=date_to)


@router.get(
    "/calls/search",
    summary="Search calls (Client)",
    description="Search across caller phone and transcript text for the authenticated business with optional date range.",
    response_model=CallListPage,
    response_description="Search results for calls.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Search results",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "call_id": "123",
                                    "business_id": "10",
                                    "business_name": "Ressy Test Kitchen",
                                    "caller_phone": "+14155551234",
                                    "duration_seconds": 320,
                                    "status": "completed",
                                    "started_at": "2024-03-01T12:00:00Z",
                                    "has_transcript": True,
                                    "summary": "Reservation created",
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
async def search_client_calls(
    q: str = Query(
        ...,
        description="Search term",
        examples={"sample": {"summary": "Query text", "value": "reservation"}},
    ),
    date_from: str | None = Query(
        None,
        description="Start date (ISO 8601)",
        examples={"sample": {"summary": "Example start", "value": "2024-03-01T00:00:00Z"}},
    ),
    date_to: str | None = Query(
        None,
        description="End date (ISO 8601)",
        examples={"sample": {"summary": "Example end", "value": "2024-03-31T23:59:59Z"}},
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=200, description="Items per page"),
    sort_by: str = Query("created_at", description="created_at or duration"),
    sort_order: str = Query("desc", description="Sort order asc/desc"),
    claims: dict = Depends(get_current_business_user),
    call_service: BusinessCallService = Depends(get_call_service),
):
    business_id = claims.get("business_id")
    if not business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access required")
    return call_service.list_calls(
        business_id=str(business_id),
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search_term=q,
    )


@router.get(
    "/calls/export",
    summary="Export calls (Client)",
    description="Export call history for the authenticated business as CSV with the same filters as listing.",
    response_description="CSV export of calls.",
    openapi_extra={
        "responses": {
            200: {
                "description": "CSV file",
                "content": {
                    "text/csv": {
                        "example": "timestamp,caller_phone,duration_seconds,status,summary\n2024-03-01T12:00:00Z,+14155551234,320,completed,Reservation created\n"
                    }
                },
            }
        }
    },
)
async def export_client_calls(
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
    status: str | None = Query(
        None,
        description="Call status filter (in_progress, completed, failed, escalated, agent_bypassed)",
        examples={"sample": {"summary": "Status", "value": "agent_bypassed"}},
    ),
    duration_min: int | None = Query(
        None, ge=0, description="Minimum duration (seconds)", examples={"sample": {"summary": "Min", "value": 30}}
    ),
    duration_max: int | None = Query(
        None, ge=0, description="Maximum duration (seconds)", examples={"sample": {"summary": "Max", "value": 600}}
    ),
    caller_phone: str | None = Query(
        None,
        description="Search by caller phone (partial)",
        examples={"sample": {"summary": "Phone", "value": "+1415555"}},
    ),
    sort_by: str = Query("created_at", description="created_at or duration"),
    sort_order: str = Query("desc", description="Sort order asc/desc"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(500, ge=1, le=1000, description="Max rows per export"),
    claims: dict = Depends(get_current_business_user),
    call_service: BusinessCallService = Depends(get_call_service),
):
    business_id = claims.get("business_id")
    if not business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access required")

    items = call_service.export_calls(
        business_id=str(business_id),
        date_from=date_from,
        date_to=date_to,
        status=status,
        duration_min=duration_min,
        duration_max=duration_max,
        caller_phone=caller_phone,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "caller_phone", "duration_seconds", "status", "summary"])
    for item in items:
        # Format phone number so Excel treats it as text and does not use scientific notation
        # Using ="phone_number" forces Excel to interpret the value as text while preserving the content
        # e.g., a value like ="+1234567890" will be displayed as +1234567890 without scientific notation
        phone_number = item.caller_phone or ""
        if phone_number:
            # Wrap in an Excel text formula to reliably preserve formatting when opened in Excel
            phone_number = f'="{phone_number}"'
        writer.writerow(
            [
                item.started_at,
                phone_number,
                item.duration_seconds,
                item.status,
                item.summary or "",
            ]
        )
    output.seek(0)

    # Add UTF-8 BOM to help Excel properly interpret the file and preserve formatting
    csv_content = output.getvalue()
    return StreamingResponse(
        iter(["\ufeff".encode("utf-8") + csv_content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="calls.csv"'},
    )


@router.get(
    "/calls/{call_id}",
    summary="Get call details (Client)",
    description="Return full call details and transcript for a call belonging to the authenticated business.",
    response_model=CallDetailResponse,
    response_description="Call detail with transcript (if available).",
    openapi_extra={
        "responses": {
            200: {
                "description": "Call detail",
                "content": {
                    "application/json": {
                        "example": {
                            "call_id": "123",
                            "business_id": "10",
                            "business_name": "Ressy Test Kitchen",
                            "caller_phone": "+14155551234",
                            "status": "completed",
                            "started_at": "2024-03-01T12:00:00Z",
                            "ended_at": "2024-03-01T12:05:20Z",
                            "duration_seconds": 320,
                            "cost": 0.12,
                            "call_direction": "inbound",
                            "has_transcript": True,
                            "transcript": [
                                {
                                    "sequence": 1,
                                    "role": "user",
                                    "content": "I want to book a table for two tonight.",
                                    "timestamp": "2024-03-01T12:00:10Z",
                                }
                            ],
                            "summary": "Reservation created",
                            "order_id": None,
                            "reservation_id": "55",
                        }
                    }
                },
            }
        }
    },
)
async def get_client_call_detail(
    call_id: str,
    claims: dict = Depends(get_current_business_user),
    call_service: BusinessCallService = Depends(get_call_service),
):
    business_id = claims.get("business_id")
    if not business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access required")
    call, forbidden = call_service.get_call_detail(call_id, business_scope=str(business_id))
    if forbidden:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Call belongs to a different business")
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return call
