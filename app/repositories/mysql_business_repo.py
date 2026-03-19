"""
MySQL Business Repository for multitenant operations.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLBusinessRepository(MySQLBaseRepository):
    """Repository for business data access in MySQL."""

    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get business by name."""
        try:
            query = """
                SELECT
                    b.id,
                    b.name,
                    b.business_type,
                    b.address,
                    b.phone_number,
                    b.twilio_phone_number,
                    b.twilio_details,
                    b.deepgram_details,
                    b.forward_minutes,
                    b.backward_minutes,
                    b.is_credit_card_required_for_reservation,
                    b.forward_escalations,
                    b.escalation_phone_number,
                    b.kill_switch_enabled,
                    b.monday_open, b.monday_close, b.monday_closed,
                    b.tuesday_open, b.tuesday_close, b.tuesday_closed,
                    b.wednesday_open, b.wednesday_close, b.wednesday_closed,
                    b.thursday_open, b.thursday_close, b.thursday_closed,
                    b.friday_open, b.friday_close, b.friday_closed,
                    b.saturday_open, b.saturday_close, b.saturday_closed,
                    b.sunday_open, b.sunday_close, b.sunday_closed,
                    b.monday_24_hours, b.tuesday_24_hours, b.wednesday_24_hours,
                    b.thursday_24_hours, b.friday_24_hours, b.saturday_24_hours, b.sunday_24_hours,
                    b.reservation_seating_capacity,
                    b.reservation_advance_days,
                    b.timezone,
                    COALESCE(bf.orders_enabled, TRUE) AS orders_enabled,
                    COALESCE(bf.reservations_enabled, TRUE) AS reservations_enabled,
                    COALESCE(bf.faqs_enabled, TRUE) AS faqs_enabled,
                    b.created_at,
                    b.updated_at
                FROM Businesses b
                LEFT JOIN Business_Features bf ON bf.business_id = b.id
                WHERE b.name = %s
                LIMIT 1
            """
            results = self._execute_query(query, (name,))
            if results:
                result = results[0]
                if "forward_escalations" not in result:
                    result["forward_escalations"] = False
                if "escalation_phone_number" not in result:
                    result["escalation_phone_number"] = None
                if "kill_switch_enabled" not in result:
                    result["kill_switch_enabled"] = False
                if "reservation_seating_capacity" not in result or result.get("reservation_seating_capacity") is None:
                    result["reservation_seating_capacity"] = 50
                if "reservation_advance_days" not in result or result.get("reservation_advance_days") is None:
                    result["reservation_advance_days"] = 30
                if "timezone" not in result:
                    result["timezone"] = None
                if "orders_enabled" not in result:
                    result["orders_enabled"] = True
                if "reservations_enabled" not in result:
                    result["reservations_enabled"] = True
                if "faqs_enabled" not in result:
                    result["faqs_enabled"] = True
                return result
            return None
        except Exception:
            query = """
                SELECT
                    id,
                    name,
                    address,
                    phone_number,
                    twilio_phone_number,
                    twilio_details,
                    deepgram_details,
                    forward_minutes,
                    backward_minutes,
                    is_credit_card_required_for_reservation,
                    created_at,
                    updated_at
                FROM Businesses
                WHERE name = %s
                LIMIT 1
            """
            results = self._execute_query(query, (name,))
            if results:
                result = results[0]
                result["forward_escalations"] = False
                result["escalation_phone_number"] = None
                result["kill_switch_enabled"] = False
                result["reservation_seating_capacity"] = 50
                result["reservation_advance_days"] = 30
                result["timezone"] = None
                result["orders_enabled"] = True
                result["reservations_enabled"] = True
                result["faqs_enabled"] = True
                # Set default operating hours for all days
                for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                    result[f"{day}_open"] = "09:00:00"
                    result[f"{day}_close"] = "22:00:00"
                    result[f"{day}_closed"] = False
                    result[f"{day}_24_hours"] = False
                return result
            return None

    def get_by_twilio_number(self, twilio_phone_number: str) -> Optional[Dict]:
        """
        Get business by Twilio phone number.
        Used for multitenant call routing.
        """
        # Try to get business with opening/closing times, fallback to basic query if columns don't exist
        try:
            query = """
                SELECT
                    b.id,
                    b.name,
                    b.business_type,
                    b.address,
                    b.phone_number,
                    b.twilio_phone_number,
                    b.twilio_details,
                    b.deepgram_details,
                    b.forward_minutes,
                    b.backward_minutes,
                    b.is_credit_card_required_for_reservation,
                    b.forward_escalations,
                    b.escalation_phone_number,
                    b.kill_switch_enabled,
                    b.monday_open, b.monday_close, b.monday_closed,
                    b.tuesday_open, b.tuesday_close, b.tuesday_closed,
                    b.wednesday_open, b.wednesday_close, b.wednesday_closed,
                    b.thursday_open, b.thursday_close, b.thursday_closed,
                    b.friday_open, b.friday_close, b.friday_closed,
                    b.saturday_open, b.saturday_close, b.saturday_closed,
                    b.sunday_open, b.sunday_close, b.sunday_closed,
                    b.monday_24_hours, b.tuesday_24_hours, b.wednesday_24_hours,
                    b.thursday_24_hours, b.friday_24_hours, b.saturday_24_hours, b.sunday_24_hours,
                    b.reservation_seating_capacity,
                    b.reservation_advance_days,
                    b.timezone,
                    COALESCE(bf.orders_enabled, TRUE) AS orders_enabled,
                    COALESCE(bf.reservations_enabled, TRUE) AS reservations_enabled,
                    COALESCE(bf.faqs_enabled, TRUE) AS faqs_enabled,
                    COALESCE(bf.orders_sms_redirect_enabled, FALSE) AS orders_sms_redirect_enabled,
                    bf.orders_redirect_url,
                    bf.orders_redirect_message,
                    COALESCE(bf.reservations_sms_redirect_enabled, FALSE) AS reservations_sms_redirect_enabled,
                    bf.reservations_redirect_url,
                    bf.reservations_redirect_message,
                    b.created_at,
                    b.updated_at
                FROM Businesses b
                LEFT JOIN Business_Features bf ON bf.business_id = b.id
                WHERE b.twilio_phone_number = %s
                LIMIT 1
            """
            results = self._execute_query(query, (twilio_phone_number,))
            if results:
                result = results[0]
                if "forward_escalations" not in result:
                    result["forward_escalations"] = False
                if "escalation_phone_number" not in result:
                    result["escalation_phone_number"] = None
                if "kill_switch_enabled" not in result:
                    result["kill_switch_enabled"] = False
                if "reservation_seating_capacity" not in result or result.get("reservation_seating_capacity") is None:
                    result["reservation_seating_capacity"] = 50
                if "reservation_advance_days" not in result or result.get("reservation_advance_days") is None:
                    result["reservation_advance_days"] = 30
                if "timezone" not in result:
                    result["timezone"] = None
                # Build nested features dict for websocket service compatibility
                result["features"] = {
                    "orders_enabled": bool(result.get("orders_enabled", True)),
                    "reservations_enabled": bool(result.get("reservations_enabled", True)),
                    "faqs_enabled": bool(result.get("faqs_enabled", True)),
                    "orders_sms_redirect": {
                        "enabled": bool(result.get("orders_sms_redirect_enabled", False)),
                        "redirect_url": result.get("orders_redirect_url"),
                        "redirect_message": result.get("orders_redirect_message"),
                    },
                    "reservations_sms_redirect": {
                        "enabled": bool(result.get("reservations_sms_redirect_enabled", False)),
                        "redirect_url": result.get("reservations_redirect_url"),
                        "redirect_message": result.get("reservations_redirect_message"),
                    },
                }
                return result
            return None
        except Exception:
            query = """
                SELECT
                    id,
                    name,
                    address,
                    phone_number,
                    twilio_phone_number,
                    twilio_details,
                    deepgram_details,
                    forward_minutes,
                    backward_minutes,
                    is_credit_card_required_for_reservation,
                    created_at,
                    updated_at
                FROM Businesses
                WHERE twilio_phone_number = %s
                LIMIT 1
            """
            results = self._execute_query(query, (twilio_phone_number,))
            if results:
                result = results[0]
                result["forward_escalations"] = False
                result["escalation_phone_number"] = None
                result["kill_switch_enabled"] = False
                result["reservation_seating_capacity"] = 50
                result["reservation_advance_days"] = 30
                result["timezone"] = None
                result["orders_enabled"] = True
                result["reservations_enabled"] = True
                result["faqs_enabled"] = True
                # Set default operating hours for all days
                for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                    result[f"{day}_open"] = "09:00:00"
                    result[f"{day}_close"] = "22:00:00"
                    result[f"{day}_closed"] = False
                    result[f"{day}_24_hours"] = False
                return result
            return None

    def get_by_id(self, business_id: int) -> Optional[Dict]:
        """
        Get business by ID.
        """
        try:
            query = """
                SELECT
                    b.id,
                    b.name,
                    b.business_type,
                    b.address,
                    b.phone_number,
                    b.twilio_phone_number,
                    b.twilio_details,
                    b.deepgram_details,
                    b.forward_minutes,
                    b.backward_minutes,
                    b.is_credit_card_required_for_reservation,
                    b.forward_escalations,
                    b.escalation_phone_number,
                    b.kill_switch_enabled,
                    b.monday_open, b.monday_close, b.monday_closed,
                    b.tuesday_open, b.tuesday_close, b.tuesday_closed,
                    b.wednesday_open, b.wednesday_close, b.wednesday_closed,
                    b.thursday_open, b.thursday_close, b.thursday_closed,
                    b.friday_open, b.friday_close, b.friday_closed,
                    b.saturday_open, b.saturday_close, b.saturday_closed,
                    b.sunday_open, b.sunday_close, b.sunday_closed,
                    b.monday_24_hours, b.tuesday_24_hours, b.wednesday_24_hours,
                    b.thursday_24_hours, b.friday_24_hours, b.saturday_24_hours, b.sunday_24_hours,
                    b.reservation_seating_capacity,
                    b.reservation_advance_days,
                    b.timezone,
                    COALESCE(bf.orders_enabled, TRUE) AS orders_enabled,
                    COALESCE(bf.reservations_enabled, TRUE) AS reservations_enabled,
                    COALESCE(bf.faqs_enabled, TRUE) AS faqs_enabled,
                    b.created_at,
                    b.updated_at
                FROM Businesses b
                LEFT JOIN Business_Features bf ON bf.business_id = b.id
                WHERE b.id = %s
                LIMIT 1
            """
            results = self._execute_query(query, (business_id,))
            if results:
                result = results[0]
                if "forward_escalations" not in result:
                    result["forward_escalations"] = False
                if "escalation_phone_number" not in result:
                    result["escalation_phone_number"] = None
                if "kill_switch_enabled" not in result:
                    result["kill_switch_enabled"] = False
                if "reservation_seating_capacity" not in result or result.get("reservation_seating_capacity") is None:
                    result["reservation_seating_capacity"] = 50
                if "reservation_advance_days" not in result or result.get("reservation_advance_days") is None:
                    result["reservation_advance_days"] = 30
                if "timezone" not in result:
                    result["timezone"] = None
                if "orders_enabled" not in result:
                    result["orders_enabled"] = True
                if "reservations_enabled" not in result:
                    result["reservations_enabled"] = True
                if "faqs_enabled" not in result:
                    result["faqs_enabled"] = True
                return result
            return None
        except Exception:
            query = """
                SELECT
                    id,
                    name,
                    address,
                    phone_number,
                    twilio_phone_number,
                    twilio_details,
                    deepgram_details,
                    forward_minutes,
                    backward_minutes,
                    is_credit_card_required_for_reservation,
                    created_at,
                    updated_at
                FROM Businesses
                WHERE id = %s
                LIMIT 1
            """
            results = self._execute_query(query, (business_id,))
            if results:
                result = results[0]
                result["forward_escalations"] = False
                result["escalation_phone_number"] = None
                result["kill_switch_enabled"] = False
                result["reservation_seating_capacity"] = 50
                result["reservation_advance_days"] = 30
                result["timezone"] = None
                result["orders_enabled"] = True
                result["reservations_enabled"] = True
                result["faqs_enabled"] = True
                # Set default operating hours for all days
                for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                    result[f"{day}_open"] = "09:00:00"
                    result[f"{day}_close"] = "22:00:00"
                    result[f"{day}_closed"] = False
                    result[f"{day}_24_hours"] = False
                return result
            return None

    def create(self, data: Dict) -> int:
        """
        Create a new business.
        Returns the created business ID.
        """
        query = """
            INSERT INTO Businesses (
                name, business_type, address, phone_number, twilio_phone_number,
                twilio_details, deepgram_details,
                forward_minutes, backward_minutes, is_credit_card_required_for_reservation,
                forward_escalations, escalation_phone_number, kill_switch_enabled,
                monday_open, monday_close, monday_closed,
                tuesday_open, tuesday_close, tuesday_closed,
                wednesday_open, wednesday_close, wednesday_closed,
                thursday_open, thursday_close, thursday_closed,
                friday_open, friday_close, friday_closed,
                saturday_open, saturday_close, saturday_closed,
                sunday_open, sunday_close, sunday_closed,
                monday_24_hours, tuesday_24_hours, wednesday_24_hours,
                thursday_24_hours, friday_24_hours, saturday_24_hours, sunday_24_hours,
                timezone, reservation_seating_capacity, reservation_advance_days,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, NOW(), NOW())
        """
        business_id = self._execute_insert(
            query,
            (
                data.get("name"),
                data.get("business_type", "restaurant"),
                data.get("address"),
                data.get("phone_number"),
                data.get("twilio_phone_number"),
                json.dumps(data.get("twilio_details")) if data.get("twilio_details") else None,
                json.dumps(data.get("deepgram_details")) if data.get("deepgram_details") else None,
                data.get("forward_minutes", 0),
                data.get("backward_minutes", 0),
                data.get("is_credit_card_required_for_reservation", False),
                data.get("forward_escalations", False),
                data.get("escalation_phone_number"),
                data.get("kill_switch_enabled", False),
                data.get("monday_open"),
                data.get("monday_close"),
                data.get("monday_closed", False),
                data.get("tuesday_open"),
                data.get("tuesday_close"),
                data.get("tuesday_closed", False),
                data.get("wednesday_open"),
                data.get("wednesday_close"),
                data.get("wednesday_closed", False),
                data.get("thursday_open"),
                data.get("thursday_close"),
                data.get("thursday_closed", False),
                data.get("friday_open"),
                data.get("friday_close"),
                data.get("friday_closed", False),
                data.get("saturday_open"),
                data.get("saturday_close"),
                data.get("saturday_closed", False),
                data.get("sunday_open"),
                data.get("sunday_close"),
                data.get("sunday_closed", False),
                data.get("monday_24_hours", False),
                data.get("tuesday_24_hours", False),
                data.get("wednesday_24_hours", False),
                data.get("thursday_24_hours", False),
                data.get("friday_24_hours", False),
                data.get("saturday_24_hours", False),
                data.get("sunday_24_hours", False),
                data.get("timezone"),
                data.get("reservation_seating_capacity", 50),
                data.get("reservation_advance_days", 30),
            ),
        )
        return business_id

    def get_all(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        is_credit_card_required: Optional[bool] = None,
        orders_enabled: Optional[bool] = None,
        reservations_enabled: Optional[bool] = None,
        faqs_enabled: Optional[bool] = None,
    ) -> Tuple[List[Dict], int]:
        """
        Get all businesss with pagination, search, and filtering.
        Returns (list of businesss, total count).
        """
        offset = (page - 1) * limit

        # Build WHERE clause
        where_conditions = []
        params = []

        if search:
            where_conditions.append("b.name LIKE %s")
            params.append(f"%{search}%")

        if is_credit_card_required is not None:
            where_conditions.append("b.is_credit_card_required_for_reservation = %s")
            params.append(is_credit_card_required)
        if orders_enabled is not None:
            where_conditions.append("COALESCE(bf.orders_enabled, TRUE) = %s")
            params.append(orders_enabled)
        if reservations_enabled is not None:
            where_conditions.append("COALESCE(bf.reservations_enabled, TRUE) = %s")
            params.append(reservations_enabled)
        if faqs_enabled is not None:
            where_conditions.append("COALESCE(bf.faqs_enabled, TRUE) = %s")
            params.append(faqs_enabled)

        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

        # Count query
        count_query = f"""
            SELECT COUNT(*) as total
            FROM Businesses b
            LEFT JOIN Business_Features bf ON bf.business_id = b.id
            {where_clause}
        """
        count_result = self._execute_query(count_query, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        query = f"""
            SELECT
                b.id,
                b.name,
                b.address,
                b.phone_number,
                b.twilio_phone_number,
                b.twilio_details,
                b.deepgram_details,
                b.forward_minutes,
                b.backward_minutes,
                b.is_credit_card_required_for_reservation,
                b.forward_escalations,
                b.escalation_phone_number,
                b.kill_switch_enabled,
                b.monday_open, b.monday_close, b.monday_closed,
                b.tuesday_open, b.tuesday_close, b.tuesday_closed,
                b.wednesday_open, b.wednesday_close, b.wednesday_closed,
                b.thursday_open, b.thursday_close, b.thursday_closed,
                b.friday_open, b.friday_close, b.friday_closed,
                b.saturday_open, b.saturday_close, b.saturday_closed,
                b.sunday_open, b.sunday_close, b.sunday_closed,
                b.monday_24_hours, b.tuesday_24_hours, b.wednesday_24_hours,
                b.thursday_24_hours, b.friday_24_hours, b.saturday_24_hours, b.sunday_24_hours,
                b.reservation_seating_capacity,
                    b.reservation_advance_days,
                    b.timezone,
                    b.business_type,
                    COALESCE(bf.orders_enabled, TRUE) AS orders_enabled,
                    COALESCE(bf.reservations_enabled, TRUE) AS reservations_enabled,
                    COALESCE(bf.faqs_enabled, TRUE) AS faqs_enabled,
                    b.created_at,
                    b.updated_at
                FROM Businesses b
                LEFT JOIN Business_Features bf ON bf.business_id = b.id
            {where_clause}
            ORDER BY b.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        results = self._execute_query(query, tuple(params))

        # Parse JSON fields
        for result in results:
            if result.get("twilio_details"):
                result["twilio_details"] = (
                    json.loads(result["twilio_details"])
                    if isinstance(result["twilio_details"], str)
                    else result["twilio_details"]
                )
            if result.get("deepgram_details"):
                result["deepgram_details"] = (
                    json.loads(result["deepgram_details"])
                    if isinstance(result["deepgram_details"], str)
                    else result["deepgram_details"]
                )

        return results, total

    def update(self, business_id: int, data: Dict) -> bool:
        """
        Update business by ID.
        Returns True if update was successful.
        """
        # Build update fields
        update_fields = []
        params = []

        if "name" in data:
            update_fields.append("name = %s")
            params.append(data["name"])
        if "business_type" in data:
            update_fields.append("business_type = %s")
            params.append(data["business_type"])
        if "address" in data:
            update_fields.append("address = %s")
            params.append(data["address"])
        if "phone_number" in data:
            update_fields.append("phone_number = %s")
            params.append(data["phone_number"])
        if "twilio_phone_number" in data:
            update_fields.append("twilio_phone_number = %s")
            params.append(data["twilio_phone_number"])
        if "twilio_details" in data:
            update_fields.append("twilio_details = %s")
            params.append(json.dumps(data["twilio_details"]) if data["twilio_details"] else None)
        if "deepgram_details" in data:
            update_fields.append("deepgram_details = %s")
            params.append(json.dumps(data["deepgram_details"]) if data["deepgram_details"] else None)
        if "forward_minutes" in data:
            update_fields.append("forward_minutes = %s")
            params.append(data["forward_minutes"])
        if "backward_minutes" in data:
            update_fields.append("backward_minutes = %s")
            params.append(data["backward_minutes"])
        if "is_credit_card_required_for_reservation" in data:
            update_fields.append("is_credit_card_required_for_reservation = %s")
            params.append(data["is_credit_card_required_for_reservation"])
        if "forward_escalations" in data:
            update_fields.append("forward_escalations = %s")
            params.append(data["forward_escalations"])
        if "escalation_phone_number" in data:
            update_fields.append("escalation_phone_number = %s")
            params.append(data["escalation_phone_number"])
        if "kill_switch_enabled" in data:
            update_fields.append("kill_switch_enabled = %s")
            params.append(data["kill_switch_enabled"])
        # Handle per-day operating hours
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if f"{day}_open" in data:
                update_fields.append(f"{day}_open = %s")
                params.append(data[f"{day}_open"])
            if f"{day}_close" in data:
                update_fields.append(f"{day}_close = %s")
                params.append(data[f"{day}_close"])
            if f"{day}_closed" in data:
                update_fields.append(f"{day}_closed = %s")
                params.append(data[f"{day}_closed"])
            if f"{day}_24_hours" in data:
                update_fields.append(f"{day}_24_hours = %s")
                params.append(data[f"{day}_24_hours"])
        if "reservation_seating_capacity" in data:
            update_fields.append("reservation_seating_capacity = %s")
            params.append(data["reservation_seating_capacity"])
        if "reservation_advance_days" in data:
            update_fields.append("reservation_advance_days = %s")
            params.append(data["reservation_advance_days"])
        if "timezone" in data:
            update_fields.append("timezone = %s")
            params.append(data["timezone"])

        if not update_fields:
            return False

        update_fields.append("updated_at = NOW()")
        params.append(business_id)

        query = f"""
            UPDATE Businesses
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def list_kill_switch_candidates(self) -> List[Dict]:
        """
        List businesss with fields required to evaluate kill-switch readiness.
        """
        query = """
            SELECT
                id,
                name,
                forward_escalations,
                escalation_phone_number,
                kill_switch_enabled
            FROM Businesses
            ORDER BY id ASC
        """
        results = self._execute_query(query)
        for row in results:
            if "forward_escalations" not in row:
                row["forward_escalations"] = False
            if "escalation_phone_number" not in row:
                row["escalation_phone_number"] = None
            if "kill_switch_enabled" not in row:
                row["kill_switch_enabled"] = False
        return results

    def count_businesss(self) -> int:
        """Return total business count."""
        query = "SELECT COUNT(*) AS count FROM Businesses"
        rows = self._execute_query(query)
        return int(rows[0].get("count", 0)) if rows else 0

    def list_kill_switch_invalid_businesss(self) -> List[Dict]:
        """
        List only businesss that cannot safely use kill-switch redirect.
        """
        query = """
            SELECT
                id,
                name,
                forward_escalations,
                escalation_phone_number
            FROM Businesses
            WHERE forward_escalations <> 1
               OR escalation_phone_number IS NULL
               OR TRIM(escalation_phone_number) = ''
            ORDER BY id ASC
        """
        results = self._execute_query(query)
        for row in results:
            if "forward_escalations" not in row:
                row["forward_escalations"] = False
            if "escalation_phone_number" not in row:
                row["escalation_phone_number"] = None
        return results

    def list_kill_switch_changed_businesss(self, enabled: bool, only_redirect_ready: bool = False) -> List[Dict]:
        """
        List businesss whose kill-switch value would change for the requested update.
        """
        clauses = ["kill_switch_enabled <> %s"]
        params: List[Any] = [enabled]
        if only_redirect_ready:
            clauses.append("forward_escalations = 1")
            clauses.append("escalation_phone_number IS NOT NULL")
            clauses.append("TRIM(escalation_phone_number) <> ''")
        where_sql = " AND ".join(clauses)
        query = f"""
            SELECT
                id,
                name,
                kill_switch_enabled
            FROM Businesses
            WHERE {where_sql}
            ORDER BY id ASC
        """
        results = self._execute_query(query, tuple(params))
        for row in results:
            if "kill_switch_enabled" not in row:
                row["kill_switch_enabled"] = False
        return results

    def set_kill_switch_all_redirect_ready(self, enabled: bool) -> int:
        """
        Set kill_switch_enabled for all redirect-ready businesss.
        Returns affected row count.
        """
        query = """
            UPDATE Businesses
            SET kill_switch_enabled = %s,
                updated_at = NOW()
            WHERE forward_escalations = 1
              AND escalation_phone_number IS NOT NULL
              AND TRIM(escalation_phone_number) <> ''
              AND kill_switch_enabled <> %s
        """
        return self._execute_update(query, (enabled, enabled))

    def set_kill_switch_all(self, enabled: bool) -> int:
        """
        Set kill_switch_enabled for all businesss.
        Returns affected row count.
        """
        query = """
            UPDATE Businesses
            SET kill_switch_enabled = %s,
                updated_at = NOW()
            WHERE kill_switch_enabled <> %s
        """
        return self._execute_update(query, (enabled, enabled))

    def set_kill_switch_for_ids(self, business_ids: List[int], enabled: bool) -> int:
        """
        Set kill_switch_enabled for a specific set of business IDs.
        Returns affected row count.
        """
        if not business_ids:
            return 0
        placeholders = ", ".join(["%s"] * len(business_ids))
        query = f"""
            UPDATE Businesses
            SET kill_switch_enabled = %s,
                updated_at = NOW()
            WHERE id IN ({placeholders})
              AND kill_switch_enabled <> %s
        """
        params = [enabled, *business_ids, enabled]
        return self._execute_update(query, tuple(params))

    def delete(self, business_id: int) -> bool:
        """
        Delete business by ID.
        Returns True if deletion was successful.
        """
        query = "DELETE FROM Businesses WHERE id = %s"
        affected = self._execute_update(query, (business_id,))
        return affected > 0

    def get_statistics(self, business_id: int) -> Dict:
        """
        Get statistics for a business.
        Returns dictionary with various counts.
        """
        stats = {}

        # Total menu items
        menu_query = "SELECT COUNT(*) as count FROM Catalogue WHERE business_id = %s"
        menu_result = self._execute_query(menu_query, (business_id,))
        stats["total_catalogue_items"] = menu_result[0]["count"] if menu_result else 0

        # Available menu items
        available_query = "SELECT COUNT(*) as count FROM Catalogue WHERE business_id = %s AND is_available = TRUE"
        available_result = self._execute_query(available_query, (business_id,))
        stats["available_catalogue_items"] = available_result[0]["count"] if available_result else 0

        # Special items count
        special_query = "SELECT COUNT(*) as count FROM Catalogue WHERE business_id = %s AND is_special = TRUE"
        special_result = self._execute_query(special_query, (business_id,))
        stats["special_catalogue_items_count"] = special_result[0]["count"] if special_result else 0

        # Total Business_FAQs
        faq_query = "SELECT COUNT(*) as count FROM Business_FAQs WHERE business_id = %s"
        faq_result = self._execute_query(faq_query, (business_id,))
        stats["total_faqs"] = faq_result[0]["count"] if faq_result else 0

        # Total administrators
        admin_query = "SELECT COUNT(*) as count FROM Business_Administrators WHERE business_id = %s"
        admin_result = self._execute_query(admin_query, (business_id,))
        stats["total_administrators"] = admin_result[0]["count"] if admin_result else 0

        # Total Business_Calls (business_id is VARCHAR in Business_Calls table, so convert to string)
        calls_query = "SELECT COUNT(*) as count FROM Business_Calls WHERE business_id = %s"
        calls_result = self._execute_query(calls_query, (str(business_id),))
        stats["total_calls"] = calls_result[0]["count"] if calls_result else 0

        # Total Minute Usage (sum of call_duration in minutes)
        # business_id is VARCHAR in Business_Calls table, so convert to string
        minutes_query = "SELECT COALESCE(SUM(call_duration), 0) as total_seconds FROM Business_Calls WHERE business_id = %s"
        minutes_result = self._execute_query(minutes_query, (str(business_id),))
        total_seconds = (
            minutes_result[0]["total_seconds"] if minutes_result and minutes_result[0].get("total_seconds") else 0
        )
        stats["total_minute_usage"] = round(total_seconds / 60, 2) if total_seconds else 0

        return stats
