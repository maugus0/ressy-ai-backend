from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth_middleware import get_current_admin_user
from app.models.call_models import AdminCallDetailResponse, CallAnalyticsV2, CallListPage
from app.services.call_service import CallService


def get_call_service() -> CallService:
    return CallService()


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Calls"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get(
    "/calls",
    summary="Get all calls (Admin)",
    description="Retrieve paginated call history across all restaurants with filtering, sorting, and pagination.",
    response_model=CallListPage,
    response_description="Paginated calls with restaurant metadata.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Calls retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "call_id": "123",
                                    "restaurant_id": "10",
                                    "restaurant_name": "Ressy Test Kitchen",
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
async def get_admin_calls(
    restaurant_id: str | None = Query(
        None,
        description="Filter by restaurant id",
        examples={"sample": {"summary": "Restaurant ID", "value": "10"}},
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
    sort_by: str = Query("created_at", description="created_at, duration, restaurant_id, started_at"),
    sort_order: str = Query("desc", description="Sort order asc/desc"),
    call_service: CallService = Depends(get_call_service),
):
    return call_service.list_calls(
        restaurant_id=restaurant_id,
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
    summary="Get call analytics (Admin)",
    description="Aggregated analytics across restaurants with optional restaurant filtering and required date range.",
    response_model=CallAnalyticsV2,
    response_description="Analytics totals and distributions.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Analytics summary",
                "content": {
                    "application/json": {
                        "example": {
                            "total_calls": 156,
                            "average_call_duration": 215.4,
                            "status_breakdown": {"completed": 120, "failed": 20, "abandoned": 16},
                            "time_of_day_distribution": [{"hour_bucket": 12, "count": 25}],
                            "top_restaurants": [{"restaurant_id": "10", "count": 45}],
                            "calls_by_day_of_week": [{"day_of_week": 6, "count": 40}],
                            "conversion_rates": {"orders": 0, "reservations": 0, "rate": 0},
                        }
                    }
                },
            }
        }
    },
)
async def get_admin_call_analytics(
    restaurant_id: str | None = Query(
        None,
        description="Optional restaurant filter",
        examples={"sample": {"summary": "Restaurant ID", "value": "10"}},
    ),
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
    call_service: CallService = Depends(get_call_service),
):
    return call_service.get_dashboard_analytics(restaurant_id=restaurant_id, date_from=date_from, date_to=date_to)


@router.get(
    "/calls/search",
    summary="Search calls (Admin)",
    description="Search across caller phone and transcript text with optional restaurant and date filters.",
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
                                    "restaurant_id": "10",
                                    "restaurant_name": "Ressy Test Kitchen",
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
async def search_admin_calls(
    q: str = Query(..., description="Search term", examples={"sample": {"summary": "Query text", "value": "book"}}),
    restaurant_id: str | None = Query(
        None, description="Optional restaurant filter", examples={"sample": {"summary": "Restaurant ID", "value": "10"}}
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
    sort_by: str = Query("created_at", description="created_at, duration, restaurant_id, started_at"),
    sort_order: str = Query("desc", description="Sort order asc/desc"),
    call_service: CallService = Depends(get_call_service),
):
    return call_service.list_calls(
        restaurant_id=restaurant_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search_term=q,
    )


@router.get(
    "/calls/{call_id}",
    summary="Get call details (Admin)",
    description="Return full call details, metadata, and transcript for the specified call.",
    response_model=AdminCallDetailResponse,
    response_description="Call detail with transcript (if available).",
    openapi_extra={
        "responses": {
            200: {
                "description": "Call detail",
                "content": {
                    "application/json": {
                        "example": {
                            "call_id": "123",
                            "restaurant_id": "10",
                            "restaurant_name": "Ressy Test Kitchen",
                            "caller_phone": "+14155551234",
                            "status": "completed",
                            "started_at": "2024-03-01T12:00:00Z",
                            "ended_at": "2024-03-01T12:05:20Z",
                            "duration_seconds": 320,
                            "twilio_cost": 0.096,
                            "deepgram_cost": 0.4266666667,
                            "ressy_cost": 0.5226666667,
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
async def get_admin_call_detail(call_id: str, call_service: CallService = Depends(get_call_service)):
    call = call_service.get_admin_call_detail(call_id)
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return call


@router.delete(
    "/calls/{call_id}",
    summary="Delete call (Admin)",
    description="Delete a call record and its transcript.",
    response_description="Confirmation message.",
    openapi_extra={
        "responses": {
            200: {"description": "Deleted", "content": {"application/json": {"example": {"message": "Call deleted"}}}},
            404: {"description": "Not found"},
        }
    },
)
async def delete_admin_call(call_id: str, call_service: CallService = Depends(get_call_service)):
    deleted = call_service.delete_call(call_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return {"message": "Call deleted"}


@router.delete(
    "/calls/{call_id}/transcript",
    summary="Delete transcript (Admin)",
    description="Delete only the transcript for the specified call.",
    response_description="Confirmation message.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Transcript deleted",
                "content": {"application/json": {"example": {"message": "Transcript deleted"}}},
            },
            404: {"description": "Not found"},
        }
    },
)
async def delete_admin_call_transcript(call_id: str, call_service: CallService = Depends(get_call_service)):
    updated = call_service.delete_call_transcript(call_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    return {"message": "Transcript deleted"}
