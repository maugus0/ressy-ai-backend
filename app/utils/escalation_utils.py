from __future__ import annotations


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
        "reason": row.get("reason"),
        "status": row.get("status") or "raised",
        "requested_at": str(row.get("requested_at")) if row.get("requested_at") is not None else None,
        "forwarded_at": str(row.get("forwarded_at")) if row.get("forwarded_at") is not None else None,
        "created_at": str(row.get("created_at")) if row.get("created_at") is not None else None,
        "updated_at": str(row.get("updated_at")) if row.get("updated_at") is not None else None,
    }
