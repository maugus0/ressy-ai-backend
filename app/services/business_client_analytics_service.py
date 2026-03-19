"""
Client Analytics Service for business dashboard insights.

Provides aggregated analytics data for business clients including:
- Call statistics
- Reservation statistics
- Order statistics
- Menu statistics
- FAQ statistics
- Recent activity
- Today's schedule
- Pending orders
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.repositories.mysql_call_repo import MySQLCallRepository
from app.repositories.mysql_faq_repo import MySQLFAQRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_reservation_repo import MySQLReservationRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.utils.timezone import isoformat_z

logger = logging.getLogger(__name__)


class BusinessClientAnalyticsService:
    """
    Service for generating business analytics for client dashboards.
    """

    def __init__(self):
        # Initialize repository instances once; they use connection pooling so
        # reusing them avoids unnecessary allocations without causing stale data.
        self._call_repo = MySQLCallRepository()
        self._order_repo = MySQLOrderRepository()
        self._reservation_repo = MySQLReservationRepository()
        self._menu_repo = MySQLMenuRepository()
        self._faq_repo = MySQLFAQRepository()
        self._user_repo = MySQLUserRepository()

    # ---------- Repository Factory Methods ----------
    # Return long-lived repository instances; connection pooling ensures each
    # operation uses a fresh database connection as needed.

    def _get_call_repo(self) -> MySQLCallRepository:
        """Get the call repository instance."""
        return self._call_repo

    def _get_order_repo(self) -> MySQLOrderRepository:
        """Get the order repository instance."""
        return self._order_repo

    def _get_reservation_repo(self) -> MySQLReservationRepository:
        """Get the reservation repository instance."""
        return self._reservation_repo

    def _get_menu_repo(self) -> MySQLMenuRepository:
        """Get the menu repository instance."""
        return self._menu_repo

    def _get_faq_repo(self) -> MySQLFAQRepository:
        """Get the FAQ repository instance."""
        return self._faq_repo

    def _get_user_repo(self) -> MySQLUserRepository:
        """Get the user repository instance."""
        return self._user_repo

    def _get_today_start(self) -> datetime:
        """Get the start of today with consistent timezone handling (UTC)."""
        return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    def _get_today_end(self) -> datetime:
        """Get the end of today with consistent timezone handling (UTC)."""
        return self._get_today_start() + timedelta(days=1)

    def get_business_analytics(self, business_id: int) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a business.

        Args:
            business_id: Restaurant ID

        Returns:
            Dictionary containing all analytics data
        """
        today = self._get_today_start()
        today_str = today.strftime("%Y-%m-%d 00:00:00")

        try:
            # Get all analytics
            call_stats = self._get_call_stats(business_id, today_str)
            reservation_stats = self._get_reservation_stats(business_id, today)
            order_stats = self._get_order_stats(business_id, today)
            menu_stats = self._get_menu_stats(business_id)
            faq_stats = self._get_faq_stats(business_id)
            user_stats = self._get_user_stats(business_id)

            # Get activity data
            recent_activity = self._get_recent_activity(business_id, limit=10)
            todays_schedule = self._get_todays_schedule(business_id, today)
            pending_orders = self._get_pending_orders(business_id)

            return {
                # Call statistics
                "total_calls": call_stats["total"],
                "calls_today": call_stats["today"],
                "average_call_duration": call_stats["avg_duration"],
                # Reservation statistics
                "total_reservations": reservation_stats["total"],
                "reservations_today": reservation_stats["today"],
                "confirmed_reservations": reservation_stats["confirmed"],
                "pending_reservations": reservation_stats["pending"],
                # Order statistics
                "total_orders": order_stats["total"],
                "orders_today": order_stats["today"],
                "total_revenue": order_stats["total_revenue"],
                "revenue_today": order_stats["revenue_today"],
                "pending_orders_count": order_stats["pending_count"],
                # Menu statistics
                "total_menu_items": menu_stats["total"],
                "available_menu_items": menu_stats["available"],
                "special_items": menu_stats["specials"],
                "menu_categories": menu_stats["categories"],
                # FAQ statistics
                "total_faqs": faq_stats["total"],
                # User/Caller statistics
                "total_customers": user_stats["total"],
                # Activity data
                "recent_activity": recent_activity,
                "todays_schedule": todays_schedule,
                "pending_orders": pending_orders,
            }
        except Exception as e:
            logger.error(f"Error fetching analytics for business {business_id}: {e}")
            raise

    def get_call_analytics(self, business_id: int) -> Dict[str, Any]:
        """Get detailed call analytics for a business."""
        today = self._get_today_start()
        today_str = today.strftime("%Y-%m-%d 00:00:00")

        try:
            stats = self._get_call_stats(business_id, today_str)

            # Get call analytics with time distribution
            call_repo = self._get_call_repo()
            analytics = call_repo.get_call_analytics(
                business_id=str(business_id),
            )

            return {
                "total_calls": stats["total"],
                "calls_today": stats["today"],
                "average_call_duration": stats["avg_duration"],
                "status_breakdown": analytics.get("status_breakdown", {}),
                "time_of_day_distribution": analytics.get("time_of_day_distribution", []),
                "calls_by_day_of_week": analytics.get("calls_by_day_of_week", []),
            }
        except Exception as e:
            logger.error(f"Error fetching call analytics for business {business_id}: {e}")
            raise

    def get_reservation_analytics(self, business_id: int) -> Dict[str, Any]:
        """Get detailed reservation analytics for a business."""
        today = self._get_today_start()

        try:
            stats = self._get_reservation_stats(business_id, today)

            return {
                "total_reservations": stats["total"],
                "reservations_today": stats["today"],
                "confirmed_reservations": stats["confirmed"],
                "pending_reservations": stats["pending"],
                "cancelled_reservations": stats["cancelled"],
                "completed_reservations": stats["completed"],
                "no_show_reservations": stats["no_show"],
            }
        except Exception as e:
            logger.error(f"Error fetching reservation analytics for business {business_id}: {e}")
            raise

    def get_order_analytics(self, business_id: int) -> Dict[str, Any]:
        """Get detailed order analytics for a business."""
        today = self._get_today_start()

        try:
            stats = self._get_order_stats(business_id, today)

            return {
                "total_orders": stats["total"],
                "orders_today": stats["today"],
                "total_revenue": stats["total_revenue"],
                "revenue_today": stats["revenue_today"],
                "pending_orders": stats["pending_count"],
                "confirmed_orders": stats["confirmed_count"],
                "preparing_orders": stats["preparing_count"],
                "completed_orders": stats["completed_count"],
                "cancelled_orders": stats["cancelled_count"],
            }
        except Exception as e:
            logger.error(f"Error fetching order analytics for business {business_id}: {e}")
            raise

    def get_menu_analytics(self, business_id: int) -> Dict[str, Any]:
        """Get detailed menu analytics for a business."""
        try:
            stats = self._get_menu_stats(business_id)

            return {
                "total_menu_items": stats["total"],
                "available_menu_items": stats["available"],
                "unavailable_menu_items": stats["total"] - stats["available"],
                "special_items": stats["specials"],
                "categories": stats["categories"],
                "category_count": len(stats["categories"]) if stats["categories"] else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching menu analytics for business {business_id}: {e}")
            raise

    # ---------- Private helper methods ----------

    def _get_call_stats(self, business_id: int, today_str: str) -> Dict[str, Any]:
        """Get call statistics for a business."""
        call_repo = self._get_call_repo()
        analytics = call_repo.get_call_analytics(business_id=str(business_id))
        total_calls = analytics.get("total_calls", 0)
        avg_duration = analytics.get("average_call_duration", 0)

        # Get today's calls
        today_analytics = call_repo.get_call_analytics(
            business_id=str(business_id),
            date_from=today_str,
        )
        calls_today = today_analytics.get("total_calls", 0)

        return {
            "total": total_calls,
            "today": calls_today,
            "avg_duration": round(avg_duration, 2),
        }

    def _get_reservation_stats(self, business_id: int, today: datetime) -> Dict[str, Any]:
        """Get reservation statistics for a business using efficient database queries."""
        reservation_repo = self._get_reservation_repo()
        # Use efficient aggregate query for status counts
        status_counts = reservation_repo.get_reservation_counts_by_status(business_id)

        # Calculate total from status counts
        total = sum(status_counts.values())

        # Get today's reservation count using database filtering
        today_end = today + timedelta(days=1)
        today_count = reservation_repo.count_reservations_by_business(
            business_id=business_id,
            start_date=today,
            end_date=today_end,
        )

        return {
            "total": total,
            "today": today_count,
            "confirmed": status_counts.get("confirmed", 0),
            "pending": status_counts.get("pending", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "completed": status_counts.get("completed", 0),
            "no_show": status_counts.get("no_show", 0),
        }

    def _get_order_stats(self, business_id: int, today: datetime) -> Dict[str, Any]:
        """Get order statistics for a business using efficient database queries."""
        order_repo = self._get_order_repo()
        # Total orders
        total = order_repo.count_orders_by_business(business_id)

        # Today's orders
        today_count = order_repo.count_orders_by_business(
            business_id,
            start_date=today,
        )

        # Business_Orders by status - single query instead of 5 separate queries
        status_counts = order_repo.get_order_counts_by_status(business_id)

        # Get revenue using efficient SQL SUM aggregation
        total_revenue = order_repo.calculate_revenue_by_business(business_id, status="completed")
        revenue_today = order_repo.calculate_revenue_by_business(business_id, status="completed", start_date=today)

        return {
            "total": total,
            "today": today_count,
            "total_revenue": round(total_revenue, 2),
            "revenue_today": round(revenue_today, 2),
            "pending_count": status_counts.get("pending", 0),
            "confirmed_count": status_counts.get("confirmed", 0),
            "preparing_count": status_counts.get("preparing", 0),
            "completed_count": status_counts.get("completed", 0),
            "cancelled_count": status_counts.get("cancelled", 0),
        }

    def _get_menu_stats(self, business_id: int) -> Dict[str, Any]:
        """Get menu statistics for a business."""
        menu_repo = self._get_menu_repo()
        # Get all menu items
        all_items = menu_repo.get_menus_by_business(business_id)
        total = len(all_items)

        available = 0
        specials = 0
        categories_set: set = set()

        for item in all_items:
            if item.get("is_available"):
                available += 1
            if item.get("is_special"):
                specials += 1
            category = item.get("category")
            if category:
                categories_set.add(category)

        return {
            "total": total,
            "available": available,
            "specials": specials,
            "categories": list(categories_set),
        }

    def _get_faq_stats(self, business_id: int) -> Dict[str, Any]:
        """Get FAQ statistics for a business."""
        faq_repo = self._get_faq_repo()
        faqs = faq_repo.get_by_business(business_id)
        return {"total": len(faqs)}

    def _get_user_stats(self, business_id: int) -> Dict[str, Any]:
        """Get user/customer statistics for a business."""
        user_repo = self._get_user_repo()
        count = user_repo.count_users_by_business(business_id)
        return {"total": count}

    def _get_recent_activity(self, business_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity (calls, reservations, orders) for a business."""
        activities: List[Dict[str, Any]] = []

        # Get recent calls
        call_repo = self._get_call_repo()
        calls = call_repo.get_calls_by_business(str(business_id), limit=limit)
        for call in calls:
            started_at = call.get("started_at")
            if isinstance(started_at, datetime):
                timestamp = isoformat_z(started_at)
            else:
                timestamp = str(started_at) if started_at else None
            activities.append(
                {
                    "id": call.get("id"),
                    "type": "call",
                    "description": f"Call from {call.get('caller_phone') or 'Unknown'}",
                    "status": call.get("call_status"),
                    "timestamp": timestamp,
                }
            )

        # Get recent reservations
        reservation_repo = self._get_reservation_repo()
        reservations = reservation_repo.get_reservations_by_business(
            business_id=business_id,
            limit=limit,
            offset=0,
        )
        for res in reservations:
            created_at = res.get("created_at")
            if isinstance(created_at, datetime):
                timestamp = isoformat_z(created_at)
            else:
                timestamp = str(created_at) if created_at else None
            party_size = res.get("party_size") or 0
            name = res.get("name") or "Guest"
            activities.append(
                {
                    "id": res.get("id"),
                    "type": "reservation",
                    "description": f"Table for {party_size} - {name}",
                    "status": res.get("status"),
                    "timestamp": timestamp,
                }
            )

        # Get recent orders
        order_repo = self._get_order_repo()
        orders = order_repo.get_orders_by_business(
            business_id=business_id,
            limit=limit,
            offset=0,
        )
        for order in orders:
            created_at = order.get("created_at")
            if isinstance(created_at, datetime):
                timestamp = isoformat_z(created_at)
            else:
                timestamp = str(created_at) if created_at else None
            total = order.get("total_amount") or 0
            activities.append(
                {
                    "id": order.get("id"),
                    "type": "order",
                    "description": f"Order ${total:.2f}",
                    "status": order.get("status"),
                    "timestamp": timestamp,
                }
            )

        # Sort by timestamp (most recent first) and limit
        activities.sort(
            key=lambda x: x.get("timestamp") or "",
            reverse=True,
        )

        return activities[:limit]

    def _get_todays_schedule(self, business_id: int, today: datetime) -> List[Dict[str, Any]]:
        """Get today's reservation schedule using database-level filtering."""
        reservation_repo = self._get_reservation_repo()
        today_end = today + timedelta(days=1)

        # Use database filtering for today's reservations with confirmed/pending status
        # First get confirmed reservations
        confirmed_reservations = reservation_repo.get_reservations_by_business(
            business_id=business_id,
            status="confirmed",
            start_date=today,
            end_date=today_end,
            limit=100,
            offset=0,
        )

        # Then get pending reservations
        pending_reservations = reservation_repo.get_reservations_by_business(
            business_id=business_id,
            status="pending",
            start_date=today,
            end_date=today_end,
            limit=100,
            offset=0,
        )

        # Combine and process
        all_reservations = confirmed_reservations + pending_reservations
        schedule = []

        for res in all_reservations:
            res_date = res.get("date_time")
            time_str = ""

            if res_date:
                if isinstance(res_date, datetime):
                    time_str = res_date.strftime("%H:%M")
                elif isinstance(res_date, str):
                    try:
                        parsed = datetime.fromisoformat(res_date.replace("Z", "+00:00"))
                        time_str = parsed.strftime("%H:%M")
                    except ValueError:
                        # Skip reservations with invalid date format
                        continue

            schedule.append(
                {
                    "id": res.get("id"),
                    "time": time_str,
                    "party_size": res.get("party_size") or 0,
                    "customer_name": res.get("name") or "Guest",
                    "status": res.get("status"),
                    "special_request": res.get("special_request"),
                }
            )

        # Sort by time
        schedule.sort(key=lambda x: x.get("time", ""))

        return schedule

    def _get_pending_orders(self, business_id: int) -> List[Dict[str, Any]]:
        """Get pending orders for a business."""
        order_repo = self._get_order_repo()
        orders = order_repo.get_orders_by_business(
            business_id=business_id,
            status="pending",
            limit=20,
            offset=0,
        )

        pending = []
        for order in orders:
            created_at = order.get("created_at")
            if isinstance(created_at, datetime):
                timestamp = isoformat_z(created_at)
            else:
                timestamp = str(created_at) if created_at else None
            pending.append(
                {
                    "id": order.get("id"),
                    "order_number": f"#{order.get('id')}",
                    "customer_name": order.get("customer_name") or "Guest",
                    "total": float(order.get("total_amount") or 0),
                    "status": order.get("status"),
                    "timestamp": timestamp,
                }
            )

        return pending
