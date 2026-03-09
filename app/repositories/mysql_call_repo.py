"""
MySQL Call Repository for call session operations.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger


class MySQLCallRepository(MySQLBaseRepository):
    """Repository for call data access in MySQL."""

    logger = get_logger(__name__)

    def create_call_session(
        self, user_id: str, twilio_sid: str | None, deepgram_session_id: str | None, restaurant_id: Optional[str] = None
    ) -> int:
        """
        Create a new call session and return call ID.
        """
        query = """
            INSERT INTO Calls (
                user_id, restaurant_id, twilio_call_sid, deepgram_request_id,
                call_status, call_direction, call_duration, cost, started_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
        """
        call_id = self._execute_insert(
            query, (user_id, restaurant_id, twilio_sid, deepgram_session_id, "in_progress", "inbound", 0, 0.000000)
        )
        self.logger.info(
            "[MySQL] Created call session: call_id=%s, user_id=%s, restaurant_id=%s",
            call_id,
            user_id,
            restaurant_id,
        )
        return call_id

    def update_call_cost(self, call_id: int, duration_seconds: int, ressy_cost: float) -> None:
        """
        Update call cost and duration, mark as completed unless the call was escalated.

        Note: The ressy_cost parameter should be calculated using CallService.calculate_call_costs()
        to ensure consistency. This stores ressy_cost in the database for historical reference.
        However, API endpoints (admin and client) calculate costs dynamically from current
        settings, so stored costs may become outdated if settings change.

        The stored cost is used for:
        - Historical records
        - Legacy methods (get_call_history, get_analytics_summary)

        API endpoints (get_call_detail, get_admin_call_detail) calculate costs dynamically
        and do NOT rely on stored costs.

        Args:
            call_id: Call ID to update
            duration_seconds: Call duration in seconds
            ressy_cost: Calculated Ressy cost (should come from CallService.calculate_call_costs())
        """
        query = """
            UPDATE Calls
            SET call_duration = %s,
                cost = %s,
                call_status = CASE WHEN call_status = 'escalated' THEN 'escalated' ELSE 'completed' END,
                ended_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """
        self._execute_update(query, (duration_seconds, ressy_cost, call_id))
        self.logger.info(
            "[MySQL] Updated call: call_id=%s, duration=%ss, ressy_cost=$%.6f", call_id, duration_seconds, ressy_cost
        )

    def update_call_status(self, call_id: int, status: str) -> bool:
        """
        Update call status without mutating duration or cost.
        """
        query = """
            UPDATE Calls
            SET call_status = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (status, call_id))
        self.logger.info("[MySQL] Updated call status: call_id=%s, status=%s", call_id, status)
        return affected > 0

    def finalize_call_with_status(
        self, call_id: int, status: str, duration_seconds: int = 0, cost: float = 0.0
    ) -> bool:
        """
        Finalize a call and set a specific terminal status.
        """
        query = """
            UPDATE Calls
            SET call_status = %s,
                call_duration = %s,
                cost = %s,
                ended_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (status, duration_seconds, cost, call_id))
        self.logger.info(
            "[MySQL] Finalized call: call_id=%s status=%s duration=%ss cost=%s",
            call_id,
            status,
            duration_seconds,
            cost,
        )
        return affected > 0

    def update_deepgram_request_id(self, call_id: int, deepgram_request_id: str) -> None:
        """
        Store Deepgram request/session ID for an existing call.
        """
        query = """
            UPDATE Calls
            SET deepgram_request_id = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        self._execute_update(query, (deepgram_request_id, call_id))
        self.logger.info("[MySQL] Updated deepgram_request_id for call_id=%s to %s", call_id, deepgram_request_id)

    def update_call_transcript(self, call_id: int, conversation: List[Dict]) -> None:
        """
        Persist the full conversation transcript JSON on the Calls table.
        """
        transcript_json = json.dumps({"conversation": conversation})
        query = """
            UPDATE Calls
            SET call_transcript = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        self._execute_update(query, (transcript_json, call_id))
        self.logger.info("[MySQL] Stored call transcript for call_id=%s", call_id)

    def get_user_calls(self, user_id: str, limit: int = 50) -> List[Dict]:
        query = """
            SELECT c.*, u.phone_number AS caller_phone
            FROM Calls c
            LEFT JOIN Users u ON u.id = CAST(c.user_id AS UNSIGNED)
            WHERE c.user_id = %s
            ORDER BY c.started_at DESC
            LIMIT %s
        """
        return self._execute_query(query, (user_id, limit))

    def get_calls_by_restaurant(self, restaurant_id: str, limit: int = 50) -> List[Dict]:
        query = """
            SELECT c.*, u.phone_number AS caller_phone
            FROM Calls c
            LEFT JOIN Users u ON u.id = CAST(c.user_id AS UNSIGNED)
            WHERE c.restaurant_id = %s
            ORDER BY c.started_at DESC
            LIMIT %s
        """
        return self._execute_query(query, (restaurant_id, limit))

    def get_all_calls(self, limit: int = 50) -> List[Dict]:
        query = """
            SELECT c.*, u.phone_number AS caller_phone
            FROM Calls c
            LEFT JOIN Users u ON u.id = CAST(c.user_id AS UNSIGNED)
            ORDER BY c.started_at DESC
            LIMIT %s
        """
        return self._execute_query(query, (limit,))

    def store_transcript_message(
        self, call_id: int, message_sequence: int, speaker: str, message: str, timestamp: str
    ) -> None:
        """
        Store individual transcript messages.
        Note: This stores to the conversation_history in the Transcripts table via process_and_store_data.
        Individual messages are not stored separately - they're aggregated in the transcript.
        """
        # Individual messages are stored at end-of-call via update_call_transcript.
        # This method is retained for backward compatibility.
        return None

    def get_call_by_id(self, call_id: int) -> Optional[Dict]:
        query = """
            SELECT c.*, r.name AS restaurant_name, u.phone_number AS caller_phone
            FROM Calls c
            LEFT JOIN Restaurants r ON r.id = CAST(c.restaurant_id AS UNSIGNED)
            LEFT JOIN Users u ON u.id = CAST(c.user_id AS UNSIGNED)
            WHERE c.id = %s
            LIMIT 1
        """
        rows = self._execute_query(query, (call_id,))
        return rows[0] if rows else None

    def list_calls(
        self,
        restaurant_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        duration_min: Optional[int] = None,
        duration_max: Optional[int] = None,
        caller_phone: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search_term: Optional[str] = None,
    ) -> tuple[List[Dict], int]:
        """List calls with filtering, pagination, and optional transcript search."""
        allowed_sort_columns = {
            "created_at": "c.created_at",
            "duration": "c.call_duration",
            "restaurant_id": "c.restaurant_id",
            "started_at": "c.started_at",
        }
        sort_column = allowed_sort_columns.get(sort_by, "c.created_at")
        order = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        offset = max(page - 1, 0) * limit

        where_clauses = ["1=1"]
        params: list = []

        if restaurant_id:
            where_clauses.append("c.restaurant_id = %s")
            params.append(str(restaurant_id))
        if date_from:
            where_clauses.append("c.started_at >= %s")
            params.append(date_from)
        if date_to:
            where_clauses.append("c.started_at <= %s")
            params.append(date_to)
        if status:
            where_clauses.append("c.call_status = %s")
            params.append(status)
        if duration_min is not None:
            where_clauses.append("c.call_duration >= %s")
            params.append(duration_min)
        if duration_max is not None:
            where_clauses.append("c.call_duration <= %s")
            params.append(duration_max)
        if caller_phone:
            where_clauses.append("u.phone_number LIKE %s")
            params.append(f"%{caller_phone}%")
        if search_term:
            where_clauses.append(
                "(MATCH(c.call_transcript) AGAINST (%s IN NATURAL LANGUAGE MODE) OR u.phone_number LIKE %s)"
            )
            params.extend([search_term, f"%{search_term}%"])

        where_sql = " AND ".join(where_clauses)
        base_query = f"""
            FROM Calls c
            LEFT JOIN Restaurants r ON r.id = CAST(c.restaurant_id AS UNSIGNED)
            LEFT JOIN Users u ON u.id = CAST(c.user_id AS UNSIGNED)
            WHERE {where_sql}
        """

        data_query = f"""
            SELECT
                c.*,
                r.name AS restaurant_name,
                u.phone_number AS caller_phone,
                (c.call_transcript IS NOT NULL AND c.call_transcript != '') AS has_transcript
            {base_query}
            ORDER BY {sort_column} {order}
            LIMIT %s OFFSET %s
        """
        data_params = params + [limit, offset]
        rows = self._execute_query(data_query, tuple(data_params))

        count_query = f"SELECT COUNT(*) AS total {base_query}"
        count_rows = self._execute_query(count_query, tuple(params))
        total = count_rows[0]["total"] if count_rows else 0
        return rows, total

    def delete_call(self, call_id: int) -> int:
        """Delete a call record."""
        return self._execute_update("DELETE FROM Calls WHERE id = %s", (call_id,))

    def delete_call_transcript(self, call_id: int) -> int:
        """Null out transcript for a call."""
        query = """
            UPDATE Calls
            SET call_transcript = NULL,
                updated_at = NOW()
            WHERE id = %s
        """
        return self._execute_update(query, (call_id,))

    def get_call_analytics(
        self,
        restaurant_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict:
        """Return aggregated analytics for calls."""
        where_clauses = ["1=1"]
        params: list = []
        if restaurant_id:
            where_clauses.append("restaurant_id = %s")
            params.append(str(restaurant_id))
        if date_from:
            # Normalize date format: if only date is provided (YYYY-MM-DD), add time component
            # Validate date format before normalization to prevent SQL injection
            normalized_date_from = date_from
            try:
                # Try parsing as date-only format first
                if len(date_from) == 10 and date_from.count("-") == 2:
                    datetime.strptime(date_from, "%Y-%m-%d")
                    normalized_date_from = f"{date_from} 00:00:00"
                else:
                    # Validate as datetime format
                    datetime.strptime(date_from, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # If date format is invalid, log and use as-is (will fail at DB level)
                self.logger.warning(f"Invalid date_from format: {date_from}")
            where_clauses.append("started_at >= %s")
            params.append(normalized_date_from)
        if date_to:
            # Normalize date format: if only date is provided (YYYY-MM-DD), add time component to end of day
            # Validate date format before normalization to prevent SQL injection
            normalized_date_to = date_to
            try:
                # Try parsing as date-only format first
                if len(date_to) == 10 and date_to.count("-") == 2:
                    datetime.strptime(date_to, "%Y-%m-%d")
                    normalized_date_to = f"{date_to} 23:59:59"
                else:
                    # Validate as datetime format
                    datetime.strptime(date_to, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # If date format is invalid, log and use as-is (will fail at DB level)
                self.logger.warning(f"Invalid date_to format: {date_to}")
            where_clauses.append("started_at <= %s")
            params.append(normalized_date_to)

        where_sql = " AND ".join(where_clauses)

        totals_query = f"""
            SELECT
                COUNT(*) AS total_calls,
                COALESCE(AVG(call_duration), 0) AS avg_duration,
                COALESCE(SUM(call_duration), 0) AS total_duration
            FROM Calls
            WHERE {where_sql}
        """
        totals = self._execute_query(totals_query, tuple(params))
        totals_row = totals[0] if totals else {"total_calls": 0, "avg_duration": 0, "total_duration": 0}

        status_query = f"""
            SELECT call_status, COUNT(*) AS count
            FROM Calls
            WHERE {where_sql}
            GROUP BY call_status
        """
        status_rows = self._execute_query(status_query, tuple(params))
        status_breakdown = {row["call_status"]: row["count"] for row in status_rows}

        time_of_day_query = f"""
            SELECT HOUR(started_at) AS hour_bucket, COUNT(*) AS count
            FROM Calls
            WHERE {where_sql}
            GROUP BY hour_bucket
            ORDER BY hour_bucket ASC
        """
        time_of_day_rows = self._execute_query(time_of_day_query, tuple(params))

        top_restaurants_query = f"""
            SELECT restaurant_id, COUNT(*) AS count
            FROM Calls
            WHERE {where_sql}
            GROUP BY restaurant_id
            ORDER BY count DESC
            LIMIT 10
        """
        top_restaurants_rows = self._execute_query(top_restaurants_query, tuple(params))

        day_of_week_query = f"""
            SELECT DAYOFWEEK(started_at) AS day_of_week, COUNT(*) AS count
            FROM Calls
            WHERE {where_sql}
            GROUP BY day_of_week
            ORDER BY day_of_week ASC
        """
        day_of_week_rows = self._execute_query(day_of_week_query, tuple(params))

        # Calculate conversion rates: orders and reservations created within 1 hour of call start
        # Match by user_id (from Calls.user_id to Orders.user_id) and restaurant_id
        # Only count conversions where user_id can be cast to non-negative integer and restaurant_id matches
        conversion_params = list(params)
        # Build WHERE clause with table-qualified column names for JOIN queries
        # Build directly from the same conditions to avoid fragile string replacement
        conversion_where_clauses = ["1=1"]
        if restaurant_id:
            conversion_where_clauses.append("c.restaurant_id = %s")
        if date_from:
            conversion_where_clauses.append("c.started_at >= %s")
        if date_to:
            conversion_where_clauses.append("c.started_at <= %s")
        conversion_where = " AND ".join(conversion_where_clauses)

        orders_conversion_query = f"""
            SELECT COUNT(DISTINCT c.id) AS converted_calls
            FROM Calls c
            INNER JOIN Orders o ON (
                c.user_id REGEXP '^[1-9][0-9]*$|^0$'
                AND c.restaurant_id IS NOT NULL
                AND o.user_id = CAST(c.user_id AS UNSIGNED)
                AND o.restaurant_id = CAST(c.restaurant_id AS UNSIGNED)
                AND o.created_at >= c.started_at
                AND o.created_at <= DATE_ADD(c.started_at, INTERVAL 1 HOUR)
                AND o.deleted_at IS NULL
            )
            WHERE {conversion_where}
        """
        orders_result = self._execute_query(orders_conversion_query, tuple(conversion_params))
        orders_converted = int(orders_result[0].get("converted_calls", 0)) if orders_result else 0

        reservations_conversion_query = f"""
            SELECT COUNT(DISTINCT c.id) AS converted_calls
            FROM Calls c
            INNER JOIN Reservations r ON (
                c.user_id REGEXP '^[1-9][0-9]*$|^0$'
                AND c.restaurant_id IS NOT NULL
                AND r.user_id = CAST(c.user_id AS UNSIGNED)
                AND r.created_at >= c.started_at
                AND r.created_at <= DATE_ADD(c.started_at, INTERVAL 1 HOUR)
            )
            INNER JOIN Slot_Bookings sb ON (
                sb.id = r.slot_booking_id
                AND sb.restaurant_id = CAST(c.restaurant_id AS UNSIGNED)
            )
            WHERE {conversion_where}
        """
        reservations_result = self._execute_query(reservations_conversion_query, tuple(conversion_params))
        reservations_converted = int(reservations_result[0].get("converted_calls", 0)) if reservations_result else 0

        total_calls = int(totals_row.get("total_calls") or 0)
        total_converted = orders_converted + reservations_converted
        conversion_rate = (total_converted / total_calls * 100) if total_calls > 0 else 0.0

        return {
            "total_calls": total_calls,
            "average_call_duration": float(totals_row.get("avg_duration") or 0),
            "total_duration": float(totals_row.get("total_duration") or 0),
            "status_breakdown": status_breakdown,
            "time_of_day_distribution": time_of_day_rows,
            "top_restaurants": top_restaurants_rows,
            "calls_by_day_of_week": day_of_week_rows,
            "conversion_rates": {
                "orders": orders_converted,
                "reservations": reservations_converted,
                "rate": round(conversion_rate, 2),
            },
        }
