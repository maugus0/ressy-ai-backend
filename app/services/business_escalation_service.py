from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_business_escalation_repo import MySQLEscalationRepository


class BusinessEscalationService:
    """Service layer for escalation persistence and lookup."""

    ALLOWED_STATUSES = {"raised", "forwarded", "failed", "resolved"}

    def __init__(self, business_escalation_repo: Optional[MySQLEscalationRepository] = None) -> None:
        self._repo = business_escalation_repo or MySQLEscalationRepository()

    def create_escalation(self, payload: Dict[str, Any]) -> int:
        return self._repo.create_escalation(payload)

    def get_latest_by_call_sid_and_business(
        self, twilio_call_sid: str, business_id: str
    ) -> Optional[Dict[str, Any]]:
        return self._repo.get_latest_by_call_sid_and_business(twilio_call_sid, business_id)

    def mark_forwarded(self, escalation_id: int) -> bool:
        return self._repo.update_status(escalation_id, status="forwarded", forwarded=True)

    def mark_failed(self, escalation_id: int) -> bool:
        return self._repo.update_status(escalation_id, status="failed", forwarded=False)

    def list_escalations(
        self,
        business_id: Optional[str] = None,
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

    def get_escalation(self, escalation_id: int) -> Optional[Dict[str, Any]]:
        return self._repo.get_by_id(escalation_id)

    def update_escalation_status(
        self, escalation_id: int, status: str, business_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in self.ALLOWED_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(self.ALLOWED_STATUSES))}")

        escalation = self._repo.get_by_id(escalation_id)
        if not escalation:
            return None
        if business_id and str(escalation.get("business_id")) != str(business_id):
            raise PermissionError("Restaurant access denied")

        forwarded = normalized_status == "forwarded"
        updated = self._repo.update_status(escalation_id, status=normalized_status, forwarded=forwarded)
        if not updated:
            return None
        return self._repo.get_by_id(escalation_id)
