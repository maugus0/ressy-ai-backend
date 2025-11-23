"""Build function definitions for the Deepgram agent from our Pydantic arg models.

The Voice Agent expects a list of function definitions with JSON Schema so the LLM
knows how to call them. We derive the schemas from our arg models to keep things
in sync.
"""

from __future__ import annotations

from typing import List, Dict, Any

from .functions import conversation, orders, reservations


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
    check_items_schema = orders.CheckItemsAvailabilityArgs.model_json_schema()
    res_check_avail_schema = reservations.CheckAvailabilityArgs.model_json_schema()
    update_order_details_schema = orders.UpdateOrderDetailsArgs.model_json_schema()
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
            description="Check availability of menu items for pickup order requests. Always use this just before confirming the final order.",
            schema=check_items_schema,
        ),
        _definition(
            name="create_reservation",
            description="Create a reservation for a customer including party size and datetime.",
            schema=create_res_schema,
        ),
        _definition(
            name="update_reservation",
            description="Update the latest reservation for a caller using their phone number.",
            schema=update_res_schema,
        ),
        _definition(
            name="check_reservation_availability",
            description="Check reservation availability for a party size over a date range.",
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
            description="Escalate the conversation to a human when the caller has special requests or repeated misunderstandings.",
            schema=escalate_schema,
        ),
    ]
