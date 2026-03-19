"""
Kill switch event service for SSE + persistent dashboard notifications.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from starlette.concurrency import run_in_threadpool

from app.services.notification_persistence_service import NotificationPersistenceService
from app.services.sse_service import SSEService

logger = logging.getLogger(__name__)


async def emit_kill_switch_toggled(
    *,
    restaurant_id: int,
    restaurant_name: Optional[str],
    enabled: bool,
    previous_enabled: bool,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    source: str,
    include_admin_sse: bool = True,
    persist_notification: bool = True,
) -> None:
    """
    Best-effort side effects for kill switch state changes.

    Emits:
    - SSE system event subtype=kill_switch_toggled
    - Persistent dashboard notification (Notifications table)
    """
    payload: Dict[str, Any] = {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant_name,
        "enabled": bool(enabled),
        "previous_enabled": bool(previous_enabled),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "actor_email": actor_email,
        "source": source,
    }

    try:
        await SSEService().emit_system_kill_switch_toggled(
            restaurant_id=restaurant_id,
            data=payload,
            include_admin=include_admin_sse,
        )
    except Exception as exc:
        logger.warning(
            "Kill-switch toggle: failed to emit SSE event restaurant_id=%s: %s",
            restaurant_id,
            exc,
        )

    if persist_notification:
        try:
            await run_in_threadpool(
                NotificationPersistenceService().create_notification,
                restaurant_id=restaurant_id,
                type="system",
                subtype="kill_switch_toggled",
                data=payload,
                entity_id=None,
            )
        except Exception as exc:
            logger.warning(
                "Kill-switch toggle: failed to persist notification restaurant_id=%s: %s",
                restaurant_id,
                exc,
            )


async def emit_kill_switch_toggled_bulk_for_restaurants(
    *,
    changed_restaurants: list[dict[str, Any]],
    enabled: bool,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    source: str,
    include_admin_sse: bool = False,
) -> None:
    """
    Emit per-restaurant SSE events for bulk toggle and persist notifications in one DB batch.
    """
    if not changed_restaurants:
        return

    sse_service = SSEService()
    notification_events: list[dict[str, Any]] = []

    for item in changed_restaurants:
        restaurant_id = int(item["restaurant_id"])
        payload: Dict[str, Any] = {
            "restaurant_id": restaurant_id,
            "restaurant_name": item.get("restaurant_name"),
            "enabled": bool(enabled),
            "previous_enabled": bool(item.get("previous_enabled")),
            "actor_type": actor_type,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "source": source,
            "bulk": True,
        }

        try:
            await sse_service.emit_system_kill_switch_toggled(
                restaurant_id=restaurant_id,
                data=payload,
                include_admin=include_admin_sse,
            )
        except Exception as exc:
            logger.warning(
                "Kill-switch bulk toggle: failed to emit SSE event restaurant_id=%s: %s",
                restaurant_id,
                exc,
            )

        notification_events.append(
            {
                "restaurant_id": restaurant_id,
                "data": payload,
                "entity_id": None,
            }
        )

    try:
        await run_in_threadpool(
            NotificationPersistenceService().create_system_kill_switch_toggled_bulk,
            notification_events,
        )
    except Exception as exc:
        logger.warning("Kill-switch bulk toggle: failed to persist notifications in bulk: %s", exc)


async def emit_kill_switch_toggled_bulk_for_businesss(
    *,
    changed_businesss: list[dict[str, Any]],
    enabled: bool,
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    source: str,
    include_admin_sse: bool = False,
) -> None:
    """
    Emit per-business SSE events for bulk toggle and persist notifications in one DB batch.
    """
    if not changed_businesss:
        return

    sse_service = SSEService()
    notification_events: list[dict[str, Any]] = []

    for item in changed_businesss:
        business_id = int(item["business_id"])
        payload: Dict[str, Any] = {
            "business_id": business_id,
            "business_name": item.get("business_name"),
            "enabled": bool(enabled),
            "previous_enabled": bool(item.get("previous_enabled")),
            "actor_type": actor_type,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "source": source,
            "bulk": True,
        }

        try:
            # Use business_id as restaurant_id for SSE (SSE service supports both)
            await sse_service.emit_system_kill_switch_toggled(
                restaurant_id=business_id,
                data=payload,
                include_admin=include_admin_sse,
            )
        except Exception as exc:
            logger.warning(
                "Kill-switch bulk toggle: failed to emit SSE event business_id=%s: %s",
                business_id,
                exc,
            )

        notification_events.append(
            {
                "restaurant_id": business_id,  # Notification service uses restaurant_id field
                "data": payload,
                "entity_id": None,
            }
        )

    try:
        await run_in_threadpool(
            NotificationPersistenceService().create_system_kill_switch_toggled_bulk,
            notification_events,
        )
    except Exception as exc:
        logger.warning("Kill-switch bulk toggle: failed to persist notifications in bulk: %s", exc)


async def emit_kill_switch_bulk_summary(
    *,
    enabled: bool,
    targeted_count: int,
    eligible_count: int,
    updated_count: int,
    skipped_count: int,
    skipped: list[dict[str, Any]],
    actor_type: str,
    actor_id: Optional[str],
    actor_email: Optional[str],
    source: str,
) -> None:
    """
    Emit/persist a single admin-facing summary for kill switch bulk actions.
    """
    payload: Dict[str, Any] = {
        "enabled": bool(enabled),
        "targeted_count": int(targeted_count),
        "eligible_count": int(eligible_count),
        "updated_count": int(updated_count),
        "skipped_count": int(skipped_count),
        "skipped": skipped,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "actor_email": actor_email,
        "source": source,
    }

    try:
        await SSEService().emit_system_kill_switch_bulk_updated_admin_only(data=payload)
    except Exception as exc:
        logger.warning("Kill-switch bulk summary: failed to emit admin SSE event: %s", exc)

    try:
        await run_in_threadpool(
            NotificationPersistenceService().create_notification,
            restaurant_id=None,
            type="system",
            subtype="kill_switch_bulk_updated",
            data=payload,
            entity_id=None,
        )
    except Exception as exc:
        logger.warning("Kill-switch bulk summary: failed to persist admin notification: %s", exc)
