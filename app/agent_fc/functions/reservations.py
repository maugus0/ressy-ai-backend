"""Reservation-related function implementations backed by ReservationService."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from app.repositories.mysql_reservation_repo import MySQLReservationRepository
from app.repositories.mysql_user_repo import MySQLUserRepository

_reservation_repo = MySQLReservationRepository()
_user_repo = MySQLUserRepository()


class CreateReservationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: str
    party_size: int
    datetime_iso: str
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    occasion: Optional[str] = None
    notes: Optional[str] = None


class UpdateReservationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_contact: str
    changes: Dict[str, Any]


class CheckAvailabilityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: str
    party_size: int
    date_start_iso: str
    date_end_iso: str


async def _run_service_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


async def create_reservation(**kwargs) -> Dict[str, Any]:
    args = CreateReservationArgs.model_validate(kwargs)
    print(
        f"[INFO] create_reservation invoked restaurant_id={args.restaurant_id} "
        f"party_size={args.party_size}"
    )

    async def _create():
        user_id = _user_repo.create_or_update_user(
            {
                "name": args.customer_name,
                "phone_number": args.customer_contact,
                "email": None,
                "address": None,
                "is_spam": False,
                "credit_card": None,
            }
        )
        slot_id = _reservation_repo.create_slot_booking(int(args.restaurant_id), args.datetime_iso)
        reservation = _reservation_repo.create_reservation(user_id, slot_id, status="confirmed")
        reservation["party_size"] = args.party_size
        reservation["notes"] = args.notes
        return reservation

    reservation = await _run_service_call(_create)
    return {"status": "CONFIRMED", "reservation": reservation}


async def update_reservation(**kwargs) -> Dict[str, Any]:
    args = UpdateReservationArgs.model_validate(kwargs)
    print(f"[INFO] update_reservation invoked customer_contact={args.customer_contact}")

    async def _update():
        user_id = _user_repo.get_user_id_by_phone_or_email(args.customer_contact, None)
        if not user_id:
            return None
        reservation = _reservation_repo.get_latest_by_user(user_id)
        if not reservation:
            return None
        updated_fields = dict(args.changes)
        reservation_id = reservation.get("id")
        if reservation_id:
            _reservation_repo.update_reservation(reservation_id, updated_fields)
            return _reservation_repo.get_latest_by_user(user_id)
        return None

    updated = await _run_service_call(_update)
    return {"status": "UPDATED" if updated else "NOT_FOUND", "reservation": updated}


async def check_reservation_availability(**kwargs) -> Dict[str, Any]:
    args = CheckAvailabilityArgs.model_validate(kwargs)
    print(
        f"[INFO] check_reservation_availability invoked restaurant_id={args.restaurant_id} "
        f"party_size={args.party_size}"
    )

    async def _check():
        slots = _reservation_repo.list_available_slots(int(args.restaurant_id), args.date_start_iso, args.date_end_iso)
        return {
            "restaurant_id": args.restaurant_id,
            "party_size": args.party_size,
            "available": bool(slots),
            "slots": slots[:10],
        }

    return await _run_service_call(_check)
