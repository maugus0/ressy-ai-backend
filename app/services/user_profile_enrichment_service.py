"""
User Profile Enrichment Service.

Aggregates data from Orders, Reservations, Calls, and User_Restaurant_Metadata
to update and enrich user profiles in the Users table.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_sync_repo import MySQLUserSyncRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class UserProfileEnrichmentService:
    """Service for enriching user profiles with aggregated data."""

    def __init__(self):
        self.user_repo = MySQLUserRepository()
        self.sync_repo = MySQLUserSyncRepository()

    def enrich_user_profile(self, user_id: int, conflict_strategy: str = "latest_wins") -> Dict[str, Any]:
        """
        Enrich a user's profile with aggregated data from transactions.

        Args:
            user_id: User ID to enrich
            conflict_strategy: Strategy for handling conflicts
                - "latest_wins": Use most recent data
                - "non_null_wins": Prefer non-null values
                - "source_priority": Prioritize by source (Orders > Reservations > Calls)

        Returns:
            Dictionary with enrichment results:
                - success: bool
                - updated_fields: List[str]
                - conflicts: List[Dict]
        """
        result = {
            "success": False,
            "updated_fields": [],
            "conflicts": [],
            "error": None,
        }

        try:
            # Get current user data
            current_user = self.user_repo.get_user_by_id(user_id)
            if not current_user:
                result["error"] = f"User {user_id} not found"
                return result

            # Get aggregated data
            aggregated_data = self.sync_repo.get_user_aggregated_data(user_id)

            # Determine updates needed
            updates = {}
            updated_fields = []

            # Update statistics fields from aggregated data
            # These are always overwritten with latest aggregated values
            if aggregated_data.get("orders"):
                orders_data = aggregated_data["orders"]
                # Note: We don't store order statistics in Users table directly
                # This is for future extensibility if we add statistics columns

            if aggregated_data.get("reservations"):
                reservations_data = aggregated_data["reservations"]
                # Note: We don't store reservation statistics in Users table directly
                # This is for future extensibility if we add statistics columns

            if aggregated_data.get("calls"):
                calls_data = aggregated_data["calls"]
                # Note: We don't store call statistics in Users table directly
                # This is for future extensibility if we add statistics columns

            # For now, the enrichment service ensures the user record exists and is properly linked
            # Future enhancements can update name/address from latest transactions if those fields
            # are added to Orders/Reservations/Calls tables

            # Perform the update if there are any fields to update
            if updates:
                self.user_repo.update_user(user_id, updates)
                updated_fields = list(updates.keys())

            # Mark as successful if we processed the user
            result["success"] = True
            result["updated_fields"] = updated_fields

        except Exception as e:
            logger.exception("Error enriching user profile for user_id=%s: %s", user_id, e)
            result["error"] = str(e)

        return result

    def batch_enrich_profiles(
        self,
        user_ids: List[int],
        conflict_strategy: str = "latest_wins",
    ) -> Dict[str, Any]:
        """
        Batch enrich multiple user profiles.

        Args:
            user_ids: List of user IDs to enrich
            conflict_strategy: Conflict resolution strategy

        Returns:
            Dictionary with batch results:
                - total: int
                - successful: int
                - failed: int
                - results: List[Dict]
        """
        results = {
            "total": len(user_ids),
            "successful": 0,
            "failed": 0,
            "results": [],
        }

        for user_id in user_ids:
            try:
                enrichment_result = self.enrich_user_profile(user_id, conflict_strategy)
                if enrichment_result["success"]:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                results["results"].append(
                    {
                        "user_id": user_id,
                        "success": enrichment_result["success"],
                        "error": enrichment_result.get("error"),
                    }
                )
            except Exception as e:
                logger.exception("Error in batch enrichment for user_id=%s: %s", user_id, e)
                results["failed"] += 1
                results["results"].append(
                    {
                        "user_id": user_id,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    def resolve_conflict(
        self,
        field_name: str,
        current_value: Any,
        new_value: Any,
        current_timestamp: Optional[datetime],
        new_timestamp: Optional[datetime],
        strategy: str = "latest_wins",
    ) -> Any:
        """
        Resolve a conflict between current and new field values.

        Args:
            field_name: Name of the field
            current_value: Current value in database
            new_value: New value from transaction data
            current_timestamp: Timestamp of current value
            new_timestamp: Timestamp of new value
            strategy: Conflict resolution strategy

        Returns:
            Resolved value to use
        """
        # If new value is None, keep current
        if new_value is None:
            return current_value

        # If current value is None, use new
        if current_value is None:
            return new_value

        # Both have values - apply strategy
        if strategy == "latest_wins":
            if new_timestamp and current_timestamp:
                return new_value if new_timestamp > current_timestamp else current_value
            # If timestamps unavailable, prefer new value
            return new_value

        elif strategy == "non_null_wins":
            # Prefer non-null (already handled above)
            return new_value if new_value is not None else current_value

        elif strategy == "source_priority":
            # This would require knowing the source, which we don't track here
            # Default to latest_wins
            return (
                new_value
                if new_timestamp and (not current_timestamp or new_timestamp > current_timestamp)
                else current_value
            )

        # Default: keep current
        return current_value

    def should_update_field(
        self,
        field_name: str,
        current_value: Any,
        new_value: Any,
    ) -> bool:
        """
        Determine if a field should be updated.

        Args:
            field_name: Name of the field
            current_value: Current value
            new_value: New value

        Returns:
            True if field should be updated
        """
        # Never auto-update spam status
        if field_name == "is_spam":
            return False

        # Never auto-update credit card (security)
        if field_name == "credit_card":
            return False

        # If new value is None, don't update
        if new_value is None:
            return False

        # If values are the same, don't update
        if current_value == new_value:
            return False

        # For email/phone: be careful with unique constraints
        # We'll let the repository handle constraint violations
        return True

    def get_user_enrichment_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get a summary of enrichment data for a user (without updating).

        Useful for previewing what would be updated.

        Args:
            user_id: User ID

        Returns:
            Dictionary with enrichment summary
        """
        try:
            current_user = self.user_repo.get_user_by_id(user_id)
            if not current_user:
                return {"error": "User not found"}

            aggregated = self.sync_repo.get_user_aggregated_data(user_id)

            return {
                "user_id": user_id,
                "current_profile": {
                    "name": current_user.get("name"),
                    "email": current_user.get("email"),
                    "phone_number": current_user.get("phone_number"),
                    "address": current_user.get("address"),
                    "updated_at": current_user.get("updated_at"),
                },
                "aggregated_data": aggregated,
            }
        except Exception as e:
            logger.exception("Error getting enrichment summary for user_id=%s: %s", user_id, e)
            return {"error": str(e)}
