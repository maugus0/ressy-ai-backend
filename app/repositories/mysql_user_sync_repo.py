"""
MySQL User Sync Repository for user profile synchronization operations.

Handles batch updates, conflict resolution, and sync tracking for user profiles.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger
from app.utils.timezone import json_default

logger = get_logger(__name__)


class MySQLUserSyncRepository(MySQLBaseRepository):
    """Repository for user profile synchronization operations."""

    def get_users_needing_sync(
        self, limit: int = 100, last_sync_before: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get users that need profile updates.

        Args:
            limit: Maximum number of users to return
            last_sync_before: Only return users with activity after this time
                             (if None, uses configurable window)

        Returns:
            List of user dictionaries with user_id
        """
        # Get users who have recent activity in Orders, Reservations, or Calls
        # that might have updated their profile information
        query = """
            SELECT DISTINCT u.id as user_id, u.updated_at
            FROM Users u
            WHERE u.id IN (
                -- Users with recent orders
                SELECT DISTINCT user_id
                FROM Orders
                WHERE deleted_at IS NULL
                AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)

                UNION

                -- Users with recent reservations
                SELECT DISTINCT user_id
                FROM Reservations
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)

                UNION

                -- Users with recent calls
                SELECT DISTINCT CAST(user_id AS UNSIGNED) as user_id
                FROM Calls
                WHERE user_id IS NOT NULL
                AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            )
        """
        params: List[Any] = []

        if last_sync_before:
            query += " AND (u.updated_at IS NULL OR u.updated_at < %s)"
            params.append(last_sync_before)

        query += " ORDER BY (u.updated_at IS NULL) DESC, u.updated_at ASC LIMIT %s"
        params.append(limit)

        return self._execute_query(query, tuple(params))

    def get_user_aggregated_data(self, user_id: int) -> Dict[str, Any]:
        """
        Get aggregated data for a user from Orders, Reservations, and Calls.

        Args:
            user_id: User ID

        Returns:
            Dictionary with aggregated statistics and latest data
        """
        aggregated = {
            "user_id": user_id,
            "orders": {},
            "reservations": {},
            "calls": {},
        }

        # Get order statistics
        orders_query = """
            SELECT
                COUNT(*) as total_orders,
                COALESCE(SUM(total_amount), 0) as total_spent,
                COALESCE(AVG(total_amount), 0) as avg_order_value,
                MAX(created_at) as latest_order_date,
                MIN(created_at) as first_order_date
            FROM Orders
            WHERE user_id = %s AND deleted_at IS NULL
        """
        orders_result = self._execute_query(orders_query, (user_id,))
        if orders_result:
            aggregated["orders"] = {
                "total_orders": orders_result[0].get("total_orders", 0),
                "total_spent": float(orders_result[0].get("total_spent", 0)),
                "avg_order_value": float(orders_result[0].get("avg_order_value", 0)),
                "latest_order_date": orders_result[0].get("latest_order_date"),
                "first_order_date": orders_result[0].get("first_order_date"),
            }

        # Get reservation statistics
        reservations_query = """
            SELECT
                COUNT(*) as total_reservations,
                MAX(r.created_at) as latest_reservation_date,
                MIN(r.created_at) as first_reservation_date,
                AVG(r.party_size) as avg_party_size
            FROM Reservations r
            WHERE r.user_id = %s
        """
        reservations_result = self._execute_query(reservations_query, (user_id,))
        if reservations_result:
            aggregated["reservations"] = {
                "total_reservations": reservations_result[0].get("total_reservations", 0),
                "latest_reservation_date": reservations_result[0].get("latest_reservation_date"),
                "first_reservation_date": reservations_result[0].get("first_reservation_date"),
                "avg_party_size": (
                    float(reservations_result[0].get("avg_party_size", 0))
                    if reservations_result[0].get("avg_party_size")
                    else None
                ),
            }

        # Get call statistics
        calls_query = """
            SELECT
                COUNT(*) as total_calls,
                MAX(created_at) as latest_call_date,
                MIN(created_at) as first_call_date,
                AVG(call_duration) as avg_call_duration,
                COALESCE(SUM(cost), 0) as total_call_cost
            FROM Calls
            WHERE user_id = %s
        """
        calls_result = self._execute_query(calls_query, (str(user_id),))
        if calls_result:
            aggregated["calls"] = {
                "total_calls": calls_result[0].get("total_calls", 0),
                "latest_call_date": calls_result[0].get("latest_call_date"),
                "first_call_date": calls_result[0].get("first_call_date"),
                "avg_call_duration": (
                    float(calls_result[0].get("avg_call_duration", 0))
                    if calls_result[0].get("avg_call_duration")
                    else None
                ),
                "total_call_cost": float(calls_result[0].get("total_call_cost", 0)),
            }

        # Note: Latest contact information would be extracted from most recent order/reservation/call
        # For now, we'll rely on the Users table being updated during order creation

        return aggregated

    def batch_update_user_profiles(self, updates: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Batch update multiple user profiles.

        Args:
            updates: List of update dictionaries, each containing:
                - user_id: int
                - name: Optional[str]
                - email: Optional[str]
                - address: Optional[str]
                - Other fields to update

        Returns:
            Tuple of (successful_updates, failed_updates)
        """
        successful = 0
        failed = 0

        for update in updates:
            try:
                user_id = update.get("user_id")
                if not user_id:
                    failed += 1
                    continue

                # Build dynamic update query
                fields = []
                params = []
                for key in ["name", "email", "address", "credit_card"]:
                    if key in update and update[key] is not None:
                        fields.append(f"{key} = %s")
                        params.append(update[key])

                if not fields:
                    continue  # No fields to update

                fields.append("updated_at = NOW()")
                params.append(user_id)

                query = f"UPDATE Users SET {', '.join(fields)} WHERE id = %s"
                affected = self._execute_update(query, tuple(params))

                if affected > 0:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                logger.exception("Error updating user profile in batch: %s", e)
                failed += 1
                continue

        return (successful, failed)

    def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about user profile sync operations.

        Returns:
            Dictionary with sync statistics
        """
        # Get total users
        total_users_query = "SELECT COUNT(*) as total FROM Users"
        total_result = self._execute_query(total_users_query)
        total_users = total_result[0].get("total", 0) if total_result else 0

        # Get users with recent activity
        active_users_query = """
            SELECT COUNT(DISTINCT u.id) as active
            FROM Users u
            WHERE u.id IN (
                SELECT DISTINCT user_id FROM Orders WHERE deleted_at IS NULL AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                UNION
                SELECT DISTINCT user_id FROM Reservations WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                UNION
                SELECT DISTINCT CAST(user_id AS UNSIGNED) FROM Calls WHERE user_id IS NOT NULL AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            )
        """
        active_result = self._execute_query(active_users_query)
        active_users = active_result[0].get("active", 0) if active_result else 0

        # Get latest sync job execution
        latest_job_query = """
            SELECT
                status,
                records_processed,
                records_updated,
                records_failed,
                started_at,
                completed_at,
                execution_time_seconds
            FROM Job_Execution_Logs
            WHERE job_name = 'user_profile_sync'
            ORDER BY started_at DESC
            LIMIT 1
        """
        latest_job = self._execute_query(latest_job_query)
        latest_job_data = latest_job[0] if latest_job else None

        return {
            "total_users": total_users,
            "active_users": active_users,
            "latest_job": latest_job_data,
        }

    def create_job_execution_log(
        self,
        job_name: str,
        status: str,
        records_processed: int = 0,
        records_updated: int = 0,
        records_failed: int = 0,
        error_message: Optional[str] = None,
        execution_time_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Create a job execution log entry.

        Returns:
            Log entry ID
        """
        metadata_json = json.dumps(metadata, default=json_default) if metadata else None
        # Set completed_at only if job is finished
        if status in ["completed", "failed", "cancelled"]:
            query = """
                INSERT INTO Job_Execution_Logs (
                    job_name, status, started_at, completed_at,
                    records_processed, records_updated, records_failed,
                    error_message, execution_time_seconds, metadata
                )
                VALUES (%s, %s, NOW(), NOW(), %s, %s, %s, %s, %s, %s)
            """
            params = (
                job_name,
                status,
                records_processed,
                records_updated,
                records_failed,
                error_message,
                execution_time_seconds,
                metadata_json,
            )
        else:
            query = """
                INSERT INTO Job_Execution_Logs (
                    job_name, status, started_at, completed_at,
                    records_processed, records_updated, records_failed,
                    error_message, execution_time_seconds, metadata
                )
                VALUES (%s, %s, NOW(), NULL, %s, %s, %s, %s, %s, %s)
            """
            params = (
                job_name,
                status,
                records_processed,
                records_updated,
                records_failed,
                error_message,
                execution_time_seconds,
                metadata_json,
            )
        log_id = self._execute_insert(query, params)
        return log_id

    def update_job_execution_log(
        self,
        log_id: int,
        status: Optional[str] = None,
        records_processed: Optional[int] = None,
        records_updated: Optional[int] = None,
        records_failed: Optional[int] = None,
        error_message: Optional[str] = None,
        execution_time_seconds: Optional[float] = None,
    ) -> int:
        """
        Update a job execution log entry.

        Returns:
            Number of affected rows
        """
        fields = []
        params = []

        if status:
            fields.append("status = %s")
            params.append(status)
            if status in ["completed", "failed", "cancelled"]:
                fields.append("completed_at = NOW()")

        if records_processed is not None:
            fields.append("records_processed = %s")
            params.append(records_processed)

        if records_updated is not None:
            fields.append("records_updated = %s")
            params.append(records_updated)

        if records_failed is not None:
            fields.append("records_failed = %s")
            params.append(records_failed)

        if error_message is not None:
            fields.append("error_message = %s")
            params.append(error_message)

        if execution_time_seconds is not None:
            fields.append("execution_time_seconds = %s")
            params.append(execution_time_seconds)

        if not fields:
            return 0

        params.append(log_id)
        query = f"UPDATE Job_Execution_Logs SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def get_job_execution_logs(
        self,
        job_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get job execution logs with optional filtering.

        Returns:
            List of job execution log dictionaries
        """
        query = "SELECT * FROM Job_Execution_Logs WHERE 1=1"
        params = []

        if job_name:
            query += " AND job_name = %s"
            params.append(job_name)

        if status:
            query += " AND status = %s"
            params.append(status)

        query += " ORDER BY started_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self._execute_query(query, tuple(params))

    def get_latest_job_execution(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get the latest execution log for a job."""
        query = """
            SELECT * FROM Job_Execution_Logs
            WHERE job_name = %s
            ORDER BY started_at DESC
            LIMIT 1
        """
        results = self._execute_query(query, (job_name,))
        return results[0] if results else None
