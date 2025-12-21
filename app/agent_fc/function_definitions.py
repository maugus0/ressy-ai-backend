"""Build function definitions for the Deepgram agent from our Pydantic arg models.

The Voice Agent expects a list of function definitions with JSON Schema so the LLM
knows how to call them. We derive the schemas from our arg models to keep things
in sync.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .functions import conversation, menu, orders, reservations


def _definition(name: str, description: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": schema,
    }


def get_function_definitions() -> List[Dict[str, Any]]:
    """Return function definitions suitable for Deepgram agent think.functions."""

    create_order_schema = orders.CreateOrderArgs.model_json_schema()
    lookup_order_schema = orders.LookupOrderArgs.model_json_schema()
    create_res_schema = reservations.CreateReservationArgs.model_json_schema()
    update_res_schema = reservations.UpdateReservationArgs.model_json_schema()
    lookup_res_schema = reservations.LookupReservationArgs.model_json_schema()
    check_items_schema = orders.CheckItemsAvailabilityArgs.model_json_schema()
    res_check_avail_schema = reservations.CheckAvailabilityArgs.model_json_schema()
    update_order_details_schema = orders.UpdateOrderDetailsArgs.model_json_schema()
    list_menu_schema = menu.ListMenuArgs.model_json_schema()
    menu_item_details_schema = menu.GetMenuItemDetailsArgs.model_json_schema()
    filler_schema = conversation.AgentFillerArgs.model_json_schema()
    end_call_schema = conversation.EndCallArgs.model_json_schema()
    escalate_schema = conversation.EscalateToHumanArgs.model_json_schema()

    return [
        _definition(
            name="create_order",
            description="Create a new order for a customer with item list and optional notes.",
            schema=create_order_schema,
        ),
        _definition(
            name="lookup_order",
            description="Look up the latest order for a caller using their phone number.",
            schema=lookup_order_schema,
        ),
        _definition(
            name="update_order_details",
            description="Update the most recent order details for the caller (quantities, items, customization).",
            schema=update_order_details_schema,
        ),
        _definition(
            name="check_items_availability",
            description="Check availability of menu items for pickup order requests. ALWAYS use this before creating/updating the final order. "
            "If the intent is determined, no need to confirm with user again, call the subsequent agent function right after a successful response from this function call.",
            schema=check_items_schema,
        ),
        _definition(
            name="list_menu_items",
            description="Fetch the FULL available menu ONLY ONCE for this restaurant, including all categories and item names with IDs, when the caller asks about the menu. "
            "Since this is a potentially slow lookup, use the agent_filler function right before calling this function and then call this immediately. "
            "Re-use the response whenever asked about the menu again.",
            schema=list_menu_schema,
        ),
        _definition(
            name="get_menu_item_details",
            description="Retrieve price/description/prep-time details for a specific menu item by item_id, or search the restaurant menu by search_term.",
            schema=menu_item_details_schema,
        ),
        _definition(
            name="create_reservation",
            description="Create a table reservation for a customer. Use after gathering: date/time, party size, customer name, and contact. "
            "The reservation will be submitted as pending for restaurant confirmation.",
            schema=create_res_schema,
        ),
        _definition(
            name="lookup_reservation",
            description="Look up the latest reservation for a caller using their phone number.",
            schema=lookup_res_schema,
        ),
        _definition(
            name="update_reservation",
            description="Update the latest reservation for a caller. Requires customer_contact (phone number). "
            "Optional fields to update: party_size (number of guests), datetime_iso (new date/time in ISO format), "
            "special_request (dietary needs, preferences), notes (additional info).",
            schema=update_res_schema,
        ),
        _definition(
            name="check_reservation_availability",
            description="Check if a table is available for a party size at a specific date/time range. "
            "Use this BEFORE creating a reservation to verify the timeslot is open.",
            schema=res_check_avail_schema,
        ),
        _definition(
            name="agent_filler",
            description="ALWAYS use this before any potentially slow lookups (menu, reservations, totals) so the caller hears a natural filler. "
            "Another client-side function call should ALWAYS be followed by this function call.",
            schema=filler_schema,
        ),
        _definition(
            name="end_call",
            description="ALWAYS ALWAYS use this when a call is supposed to end. Either after all tasks are complete OR the caller indicates that the conversation is over. "
            "Farewell message will be supplied to you with this function.",
            schema=end_call_schema,
        ),
        _definition(
            name="escalate_to_human",
            description="Escalate the conversation to a human when the caller has special requests or repeated misunderstandings."
            "Use this function for large orders (more than 20 items) or reservations (pary size more than 10). "
            "This can also be used to flag suspected spam callers.",
            schema=escalate_schema,
        ),
    ]
