from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_escalation_repo import MySQLEscalationRepository


class EscalationService:
    """Service layer for escalation persistence and lookup."""

    ALLOWED_STATUSES = {"raised", "forwarded", "failed", "resolved"}

    def __init__(self, escalation_repo: Optional[MySQLEscalationRepository] = None) -> None:
        self._repo = escalation_repo or MySQLEscalationRepository()

    def create_escalation(self, payload: Dict[str, Any]) -> int:
        return self._repo.create_escalation(payload)

    def get_latest_by_call_sid_and_restaurant(
        self, twilio_call_sid: str, restaurant_id: str
    ) -> Optional[Dict[str, Any]]:
        return self._repo.get_latest_by_call_sid_and_restaurant(twilio_call_sid, restaurant_id)

    def mark_forwarded(self, escalation_id: int) -> bool:
        return self._repo.update_status(escalation_id, status="forwarded", forwarded=True)

    def mark_failed(self, escalation_id: int) -> bool:
        return self._repo.update_status(escalation_id, status="failed", forwarded=False)

    def list_escalations(
        self,
        restaurant_id: Optional[str] = None,
        status: Optional[str] = None,
        urgency: Optional[str] = None,
        reason: Optional[str] = None,
        caller_phone: Optional[str] = None,
        call_id: Optional[str] = None,
        call_sid: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "requested_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Dict[str, Any]], int]:
        return self._repo.list_escalations(
            restaurant_id=restaurant_id,
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

    def get_escalation(self, escalation_id: int) -> Optional[Dict[str, Any]]:
        return self._repo.get_by_id(escalation_id)

    def update_escalation_status(
        self, escalation_id: int, status: str, restaurant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in self.ALLOWED_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(self.ALLOWED_STATUSES))}")

        escalation = self._repo.get_by_id(escalation_id)
        if not escalation:
            return None
        if restaurant_id and str(escalation.get("restaurant_id")) != str(restaurant_id):
            raise PermissionError("Restaurant access denied")

        forwarded = normalized_status == "forwarded"
        updated = self._repo.update_status(escalation_id, status=normalized_status, forwarded=forwarded)
        if not updated:
            return None
        return self._repo.get_by_id(escalation_id)
