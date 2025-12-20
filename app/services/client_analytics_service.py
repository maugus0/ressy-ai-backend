"""
Client Analytics Service for restaurant dashboard insights.

Provides aggregated analytics data for restaurant clients including:
- Call statistics
- Reservation statistics
- Order statistics
- Menu statistics
- FAQ statistics
- Recent activity
- Today's schedule
- Pending orders
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_call_repo import MySQLCallRepository
from app.repositories.mysql_faq_repo import MySQLFAQRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_reservation_repo import MySQLReservationRepository
from app.repositories.mysql_user_repo import MySQLUserRepository


class ClientAnalyticsService:
    """Service for generating restaurant analytics for client dashboards."""

    def __init__(self):
        self.call_repo = MySQLCallRepository()
        self.order_repo = MySQLOrderRepository()
        self.reservation_repo = MySQLReservationRepository()
        self.menu_repo = MySQLMenuRepository()
        self.faq_repo = MySQLFAQRepository()
        self.user_repo = MySQLUserRepository()

    def get_restaurant_analytics(self, restaurant_id: int) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a restaurant.

        Args:
            restaurant_id: Restaurant ID

        Returns:
            Dictionary containing all analytics data
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = today.strftime("%Y-%m-%d 00:00:00")

        # Get all analytics in parallel-style (sequential but organized)
        call_stats = self._get_call_stats(restaurant_id, today_str)
        reservation_stats = self._get_reservation_stats(restaurant_id, today)
        order_stats = self._get_order_stats(restaurant_id, today)
        menu_stats = self._get_menu_stats(restaurant_id)
        faq_stats = self._get_faq_stats(restaurant_id)
        user_stats = self._get_user_stats(restaurant_id)

        # Get activity data
        recent_activity = self._get_recent_activity(restaurant_id, limit=10)
        todays_schedule = self._get_todays_schedule(restaurant_id, today)
        pending_orders = self._get_pending_orders(restaurant_id)

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

    def get_call_analytics(self, restaurant_id: int) -> Dict[str, Any]:
        """Get detailed call analytics for a restaurant."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = today.strftime("%Y-%m-%d 00:00:00")

        stats = self._get_call_stats(restaurant_id, today_str)

        # Get call analytics with time distribution
        analytics = self.call_repo.get_call_analytics(
            restaurant_id=str(restaurant_id),
        )

        return {
            "total_calls": stats["total"],
            "calls_today": stats["today"],
            "average_call_duration": stats["avg_duration"],
            "status_breakdown": analytics.get("status_breakdown", {}),
            "time_of_day_distribution": analytics.get("time_of_day_distribution", []),
            "calls_by_day_of_week": analytics.get("calls_by_day_of_week", []),
        }

    def get_reservation_analytics(self, restaurant_id: int) -> Dict[str, Any]:
        """Get detailed reservation analytics for a restaurant."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        stats = self._get_reservation_stats(restaurant_id, today)

        return {
            "total_reservations": stats["total"],
            "reservations_today": stats["today"],
            "confirmed_reservations": stats["confirmed"],
            "pending_reservations": stats["pending"],
            "cancelled_reservations": stats["cancelled"],
            "completed_reservations": stats["completed"],
            "no_show_reservations": stats["no_show"],
        }

    def get_order_analytics(self, restaurant_id: int) -> Dict[str, Any]:
        """Get detailed order analytics for a restaurant."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        stats = self._get_order_stats(restaurant_id, today)

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

    def get_menu_analytics(self, restaurant_id: int) -> Dict[str, Any]:
        """Get detailed menu analytics for a restaurant."""
        stats = self._get_menu_stats(restaurant_id)

        return {
            "total_menu_items": stats["total"],
            "available_menu_items": stats["available"],
            "unavailable_menu_items": stats["total"] - stats["available"],
            "special_items": stats["specials"],
            "categories": stats["categories"],
            "category_count": len(stats["categories"]) if stats["categories"] else 0,
        }

    # ---------- Private helper methods ----------

    def _get_call_stats(self, restaurant_id: int, today_str: str) -> Dict[str, Any]:
        """Get call statistics for a restaurant."""
        analytics = self.call_repo.get_call_analytics(restaurant_id=str(restaurant_id))
        total_calls = analytics.get("total_calls", 0)
        avg_duration = analytics.get("average_call_duration", 0)

        # Get today's calls
        today_analytics = self.call_repo.get_call_analytics(
            restaurant_id=str(restaurant_id),
            date_from=today_str,
        )
        calls_today = today_analytics.get("total_calls", 0)

        return {
            "total": total_calls,
            "today": calls_today,
            "avg_duration": round(avg_duration, 2),
        }

    def _get_reservation_stats(self, restaurant_id: int, today: datetime) -> Dict[str, Any]:
        """Get reservation statistics for a restaurant."""
        # Get all reservations for the restaurant
        all_reservations = self.reservation_repo.get_reservations_by_restaurant(
            restaurant_id=restaurant_id,
            limit=10000,  # Get all
            offset=0,
        )

        total = len(all_reservations)
        today_count = 0
        confirmed = 0
        pending = 0
        cancelled = 0
        completed = 0
        no_show = 0

        today_date = today.date()

        for res in all_reservations:
            status = res.get("status", "").lower()
            if status == "confirmed":
                confirmed += 1
            elif status == "pending":
                pending += 1
            elif status == "cancelled":
                cancelled += 1
            elif status == "completed":
                completed += 1
            elif status == "no_show":
                no_show += 1

            # Check if reservation is for today
            res_date = res.get("date_time")
            if res_date:
                if isinstance(res_date, datetime):
                    if res_date.date() == today_date:
                        today_count += 1
                elif isinstance(res_date, str):
                    try:
                        parsed_date = datetime.fromisoformat(res_date.replace("Z", "+00:00"))
                        if parsed_date.date() == today_date:
                            today_count += 1
                    except ValueError:
                        pass

        return {
            "total": total,
            "today": today_count,
            "confirmed": confirmed,
            "pending": pending,
            "cancelled": cancelled,
            "completed": completed,
            "no_show": no_show,
        }

    def _get_order_stats(self, restaurant_id: int, today: datetime) -> Dict[str, Any]:
        """Get order statistics for a restaurant."""
        # Total orders
        total = self.order_repo.count_orders_by_restaurant(restaurant_id)

        # Today's orders
        today_count = self.order_repo.count_orders_by_restaurant(
            restaurant_id,
            start_date=today,
        )

        # Orders by status
        pending_count = self.order_repo.count_orders_by_restaurant(restaurant_id, status="pending")
        confirmed_count = self.order_repo.count_orders_by_restaurant(restaurant_id, status="confirmed")
        preparing_count = self.order_repo.count_orders_by_restaurant(restaurant_id, status="preparing")
        completed_count = self.order_repo.count_orders_by_restaurant(restaurant_id, status="completed")
        cancelled_count = self.order_repo.count_orders_by_restaurant(restaurant_id, status="cancelled")

        # Get revenue (sum of total_amount for completed orders)
        total_revenue = self._calculate_revenue(restaurant_id)
        revenue_today = self._calculate_revenue(restaurant_id, start_date=today)

        return {
            "total": total,
            "today": today_count,
            "total_revenue": round(total_revenue, 2),
            "revenue_today": round(revenue_today, 2),
            "pending_count": pending_count,
            "confirmed_count": confirmed_count,
            "preparing_count": preparing_count,
            "completed_count": completed_count,
            "cancelled_count": cancelled_count,
        }

    def _calculate_revenue(self, restaurant_id: int, start_date: Optional[datetime] = None) -> float:
        """Calculate total revenue for a restaurant."""
        # Get orders and sum total_amount for completed orders
        orders = self.order_repo.get_orders_by_restaurant(
            restaurant_id=restaurant_id,
            status="completed",
            start_date=start_date,
            limit=10000,
            offset=0,
        )

        total = 0.0
        for order in orders:
            amount = order.get("total_amount")
            if amount:
                total += float(amount)

        return total

    def _get_menu_stats(self, restaurant_id: int) -> Dict[str, Any]:
        """Get menu statistics for a restaurant."""
        # Get all menu items
        all_items = self.menu_repo.get_menus_by_restaurant(restaurant_id)
        total = len(all_items)

        available = 0
        specials = 0
        categories_set = set()

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

    def _get_faq_stats(self, restaurant_id: int) -> Dict[str, Any]:
        """Get FAQ statistics for a restaurant."""
        faqs = self.faq_repo.get_by_restaurant(restaurant_id)
        return {"total": len(faqs)}

    def _get_user_stats(self, restaurant_id: int) -> Dict[str, Any]:
        """Get user/customer statistics for a restaurant."""
        count = self.user_repo.count_users_by_restaurant(restaurant_id)
        return {"total": count}

    def _get_recent_activity(self, restaurant_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity (calls, reservations, orders) for a restaurant."""
        activities: List[Dict[str, Any]] = []

        # Get recent calls
        calls = self.call_repo.get_calls_by_restaurant(str(restaurant_id), limit=limit)
        for call in calls:
            activities.append(
                {
                    "id": call.get("id"),
                    "type": "call",
                    "description": f"Call from {call.get('caller_phone', 'Unknown')}",
                    "status": call.get("call_status"),
                    "timestamp": str(call.get("started_at")) if call.get("started_at") else None,
                }
            )

        # Get recent reservations
        reservations = self.reservation_repo.get_reservations_by_restaurant(
            restaurant_id=restaurant_id,
            limit=limit,
            offset=0,
        )
        for res in reservations:
            party_size = res.get("party_size", 0)
            name = res.get("name", "Guest")
            activities.append(
                {
                    "id": res.get("id"),
                    "type": "reservation",
                    "description": f"Table for {party_size} - {name}",
                    "status": res.get("status"),
                    "timestamp": str(res.get("created_at")) if res.get("created_at") else None,
                }
            )

        # Get recent orders
        orders = self.order_repo.get_orders_by_restaurant(
            restaurant_id=restaurant_id,
            limit=limit,
            offset=0,
        )
        for order in orders:
            total = order.get("total_amount", 0)
            activities.append(
                {
                    "id": order.get("id"),
                    "type": "order",
                    "description": f"Order ${total:.2f}",
                    "status": order.get("status"),
                    "timestamp": str(order.get("created_at")) if order.get("created_at") else None,
                }
            )

        # Sort by timestamp (most recent first) and limit
        activities.sort(
            key=lambda x: x.get("timestamp") or "",
            reverse=True,
        )

        return activities[:limit]

    def _get_todays_schedule(self, restaurant_id: int, today: datetime) -> List[Dict[str, Any]]:
        """Get today's reservation schedule."""
        # Get reservations for today
        reservations = self.reservation_repo.get_reservations_by_restaurant(
            restaurant_id=restaurant_id,
            limit=100,
            offset=0,
        )

        schedule = []
        for res in reservations:
            res_date = res.get("date_time")
            if res_date:
                # Check if it's today
                is_today = False
                time_str = ""

                if isinstance(res_date, datetime):
                    is_today = res_date.date() == today.date()
                    time_str = res_date.strftime("%H:%M")
                elif isinstance(res_date, str):
                    try:
                        parsed = datetime.fromisoformat(res_date.replace("Z", "+00:00"))
                        is_today = parsed.date() == today.date()
                        time_str = parsed.strftime("%H:%M")
                    except ValueError:
                        continue

                if is_today and res.get("status") in ["confirmed", "pending"]:
                    schedule.append(
                        {
                            "id": res.get("id"),
                            "time": time_str,
                            "party_size": res.get("party_size"),
                            "customer_name": res.get("name", "Guest"),
                            "status": res.get("status"),
                            "special_request": res.get("special_request"),
                        }
                    )

        # Sort by time
        schedule.sort(key=lambda x: x.get("time", ""))

        return schedule

    def _get_pending_orders(self, restaurant_id: int) -> List[Dict[str, Any]]:
        """Get pending orders for a restaurant."""
        orders = self.order_repo.get_orders_by_restaurant(
            restaurant_id=restaurant_id,
            status="pending",
            limit=20,
            offset=0,
        )

        pending = []
        for order in orders:
            pending.append(
                {
                    "id": order.get("id"),
                    "order_number": f"#{order.get('id')}",
                    "customer_name": order.get("customer_name", "Guest"),
                    "total": float(order.get("total_amount", 0)),
                    "status": order.get("status"),
                    "timestamp": str(order.get("created_at")) if order.get("created_at") else None,
                }
            )

        return pending
