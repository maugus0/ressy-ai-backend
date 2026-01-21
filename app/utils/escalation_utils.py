from __future__ import annotations

from typing import Optional

FEATURE_REASON_MAP = {
    "orders_disabled": "Pickup orders are disabled for Ressy.",
    "reservations_disabled": "Reservations are disabled for Ressy.",
    "faqs_disabled": "General questions and FAQs are handled by the restaurant.",
}


def format_escalation_reason(reason: Optional[str]) -> Optional[str]:
    if not reason:
        return reason
    return FEATURE_REASON_MAP.get(reason, reason)


def normalize_escalation(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "call_id": str(row.get("call_id") or ""),
        "user_id": str(row.get("user_id") or ""),
        "restaurant_id": str(row.get("restaurant_id")) if row.get("restaurant_id") is not None else None,
        "restaurant_name": row.get("restaurant_name"),
        "call_sid": row.get("twilio_call_sid") or row.get("call_sid"),
        "caller_phone": row.get("caller_phone"),
        "escalation_phone_number": row.get("escalation_phone_number"),
        "urgency": row.get("urgency"),
        "reason": format_escalation_reason(row.get("reason")),
        "status": row.get("status") or "raised",
        "requested_at": str(row.get("requested_at")) if row.get("requested_at") is not None else None,
        "forwarded_at": str(row.get("forwarded_at")) if row.get("forwarded_at") is not None else None,
        "created_at": str(row.get("created_at")) if row.get("created_at") is not None else None,
        "updated_at": str(row.get("updated_at")) if row.get("updated_at") is not None else None,
    }
