"""
Public webhook endpoints for POS providers.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.services.pos_webhook_event_service import POSWebhookEventService

router = APIRouter(prefix="/api/v1/webhooks", tags=["POS Webhooks"])


def get_pos_webhook_event_service() -> POSWebhookEventService:
    return POSWebhookEventService()


@router.post(
    "/square",
    summary="Receive Square webhook events",
    include_in_schema=False,
)
async def receive_square_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    service = get_pos_webhook_event_service()
    raw_body = await request.body()
    try:
        result = service.ingest_square_webhook(raw_body=raw_body, headers=dict(request.headers))
    except ValueError as exc:
        message = str(exc)
        if "signature" in message.lower():
            raise HTTPException(status_code=403, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc

    if result.get("should_process"):
        background_tasks.add_task(service.process_square_event, int(result["webhook_event_id"]))

    return {
        "accepted": True,
        "event_type": result.get("event_type"),
        "duplicate": result.get("is_duplicate", False),
    }
