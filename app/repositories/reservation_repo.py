from datetime import datetime
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Attr

from app.config import settings
from app.repositories.base import BaseRepository
from app.repositories.mock_data import MOCK_DATA, clone


class ReservationRepository(BaseRepository):
    """Persistence layer for reservation data."""

    def _init_tables(self) -> None:  # noqa: D401 - inherited docstring
        if self.use_mock:
            self.reservations_table = None
            return
        self.reservations_table = self.dynamodb.Table(settings.RESERVATIONS_TABLE)

    def create(self, reservation_id: str, restaurant_id: str, data: dict) -> Dict[str, Any]:
        """Insert a new reservation record."""

        item: Dict[str, Any] = {
            "reservation_id": reservation_id,
            "restaurant_id": restaurant_id,
            "SK": "RESERVATION_METADATA",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **data,
        }
        if self.use_mock:
            MOCK_DATA["reservations"][reservation_id] = item
            return clone(item)
        self._with_retries(self.reservations_table.put_item, Item=item)
        return item

    def get_by_id(self, reservation_id: str) -> Dict[str, Any]:
        """Retrieve a single reservation."""

        if self.use_mock:
            return clone(MOCK_DATA["reservations"].get(reservation_id, {}))
        resp = self._with_retries(
            self.reservations_table.get_item,
            Key={"reservation_id": reservation_id, "SK": "RESERVATION_METADATA"},
        )
        return resp.get("Item", {})

    def get_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """List reservations belonging to a restaurant."""

        if self.use_mock:
            return [clone(res) for res in MOCK_DATA["reservations"].values() if
                    res.get("restaurant_id") == restaurant_id]
        resp = self._with_retries(
            self.reservations_table.scan,
            FilterExpression=Attr("restaurant_id").eq(restaurant_id),
        )
        return resp.get("Items", [])

    def get_between(
            self,
            restaurant_id: str,
            start_iso: str,
            end_iso: str,
    ) -> List[Dict[str, Any]]:
        """Return reservations scheduled within a window [start_iso, end_iso]."""

        if self.use_mock:
            items = []
            for res in MOCK_DATA["reservations"].values():
                if (
                        res.get("restaurant_id") == restaurant_id
                        and start_iso <= res.get("reservation_datetime", "") <= end_iso
                ):
                    items.append(clone(res))
            return items
        resp = self._with_retries(
            self.reservations_table.scan,
            FilterExpression=(
                    Attr("restaurant_id").eq(restaurant_id)
                    & Attr("reservation_datetime").between(start_iso, end_iso)
            ),
        )
        return resp.get("Items", [])

    def update(self, reservation_id: str, data: dict) -> Optional[Dict[str, Any]]:
        """Update a reservation and return the merged document."""

        data = dict(data)
        data["updated_at"] = datetime.utcnow().isoformat()
        if self.use_mock:
            reservation = MOCK_DATA["reservations"].get(reservation_id)
            if reservation:
                reservation.update(data)
                MOCK_DATA["reservations"][reservation_id] = reservation
            return clone(reservation) if reservation else None
        update_expression = "SET " + ", ".join(f"#{k}=:{k}" for k in data)
        self._with_retries(
            self.reservations_table.update_item,
            Key={"reservation_id": reservation_id, "SK": "RESERVATION_METADATA"},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={f"#{k}": k for k in data},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()},
        )
        return self.get_by_id(reservation_id)

    def delete(self, reservation_id: str) -> None:
        """Delete a reservation."""

        if self.use_mock:
            MOCK_DATA["reservations"].pop(reservation_id, None)
            return
        self._with_retries(
            self.reservations_table.delete_item,
            Key={"reservation_id": reservation_id, "SK": "RESERVATION_METADATA"},
        )
