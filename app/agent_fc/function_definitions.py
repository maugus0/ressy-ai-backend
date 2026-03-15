"""Build function definitions for the Deepgram agent from our Pydantic arg models.

The Voice Agent expects a list of function definitions with JSON Schema so the LLM
knows how to call them. We derive the schemas from our arg models to keep things
in sync.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .functions import conversation, menu, orders, reservations
from .functions.function_context import NoArgs


def _definition(name: str, description: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": schema,
    }


def get_function_definitions(feature_flags: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return function definitions suitable for Deepgram agent think.functions."""
    feature_flags = feature_flags or {}
    orders_enabled = bool(feature_flags.get("orders_enabled", True))
    reservations_enabled = bool(feature_flags.get("reservations_enabled", True))
    faqs_enabled = bool(feature_flags.get("faqs_enabled", True))
    menu_enabled = orders_enabled or faqs_enabled

    # SMS redirect flags
    orders_sms_redirect_enabled = bool(feature_flags.get("orders_sms_redirect_enabled", False))
    reservations_sms_redirect_enabled = bool(feature_flags.get("reservations_sms_redirect_enabled", False))
    sms_redirect_enabled = orders_sms_redirect_enabled or reservations_sms_redirect_enabled

    create_order_schema = orders.CreateOrderArgs.model_json_schema()
    lookup_order_schema = NoArgs.model_json_schema()
    lookup_order_by_id_schema = orders.LookupOrderByIdArgs.model_json_schema()
    create_res_schema = reservations.CreateReservationArgs.model_json_schema()
    update_res_schema = reservations.UpdateReservationArgs.model_json_schema()
    lookup_res_schema = NoArgs.model_json_schema()
    check_items_schema = orders.CheckItemsAvailabilityArgs.model_json_schema()
    res_check_avail_schema = reservations.CheckAvailabilityArgs.model_json_schema()
    update_order_details_schema = orders.UpdateOrderDetailsArgs.model_json_schema()
    menu_item_details_schema = menu.GetMenuItemDetailsArgs.model_json_schema()
    # filler_schema = conversation.AgentFillerArgs.model_json_schema()
    end_call_schema = conversation.EndCallArgs.model_json_schema()
    escalate_schema = conversation.EscalateToHumanArgs.model_json_schema()

    definitions: List[Dict[str, Any]] = []

    if orders_enabled:
        definitions.extend(
            [
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
                    name="lookup_order_by_id",
                    description=(
                        "Look up a specific order by order ID. Use this when the caller provides an order ID/number "
                        "(e.g., 'What's the status of order 12345?'). Uses default call context for restaurant and caller "
                        "verification, and uses order_id from function args."
                    ),
                    schema=lookup_order_by_id_schema,
                ),
                _definition(
                    name="update_order_details",
                    description="Update the most recent order details for the caller (quantities, items, customization).",
                    schema=update_order_details_schema,
                ),
                _definition(
                    name="check_items_availability",
                    description=(
                        "Check availability of menu items for pickup order requests. ALWAYS use this before creating/updating the final order. "
                        "If the intent is determined, no need to confirm with user again, call the subsequent agent function right after a successful response from this function call."
                    ),
                    schema=check_items_schema,
                ),
            ]
        )

    if menu_enabled:
        definitions.append(
            _definition(
                name="get_menu_item_details",
                description=(
                    "Retrieve price/description/prep-time details for a specific menu item by item_id. Only use this "
                    "function when customer asks for specific details (price, description, prep time) about ONE "
                    "specific item."
                ),
                schema=menu_item_details_schema,
            )
        )
        definitions.append(
            _definition(
                name="get_menu_item_customizations",
                description=(
                    "Retrieve customization progression for one selected menu item by item_id. "
                    "Call this immediately after item selection whenever has_customizations=true, before any "
                    "customization dialogue, and do it silently in the background. "
                    "The response returns next_group (single actionable group), pending_group_id, remaining_group_ids, and deferred_group_ids. "
                    "Present only next_group to the caller. After the caller answers, call this function again with "
                    "completed_group_ids including the prior pending_group_id so the flow advances. "
                    "Do not ask about remaining/deferred groups until they are returned as next_group in a later call. "
                    "Set include_ask_if_mentioned=true only when the caller explicitly asks for additional customizations."
                ),
                schema=menu.GetMenuItemCustomizationsArgs.model_json_schema(),
            )
        )

    if reservations_enabled:
        definitions.extend(
            [
                _definition(
                    name="create_reservation",
                    description=(
                        "Create a table reservation for a customer. Use after gathering: date/time, party size, customer name, and contact. "
                        "The reservation will be submitted as pending for restaurant confirmation."
                    ),
                    schema=create_res_schema,
                ),
                _definition(
                    name="lookup_reservation",
                    description="Look up the latest reservation for a caller using their phone number.",
                    schema=lookup_res_schema,
                ),
                _definition(
                    name="update_reservation",
                    description=(
                        "Update the latest reservation for a caller using default call context for caller and restaurant. "
                        "Optional fields to update: party_size (number of guests), datetime_iso (new date/time in ISO format), "
                        "special_request (dietary needs, preferences), notes (additional info)."
                    ),
                    schema=update_res_schema,
                ),
                _definition(
                    name="check_reservation_availability",
                    description=(
                        "Check if a table is available for a party size at a specific date/time. "
                        "Use this BEFORE creating a reservation to verify the requested time is open."
                    ),
                    schema=res_check_avail_schema,
                ),
            ]
        )

    definitions.extend(
        [
            # _definition(
            #     name="agent_filler",
            #     description="""Immediately use this function in the background before initiating any slow operations (functions stamped with "SLOW") to maintain a smooth conversation flow.
            #     This function should be employed to provide natural filler dialogue, ensuring the caller feels engaged and avoid long silences.
            #     Always follow this function with the relevant client-side function to complete the task efficiently, avoiding any pauses or silence.""",
            #     schema=filler_schema,
            # ),
            _definition(
                name="end_call",
                description="ALWAYS ALWAYS use this when a call is supposed to end. Either after all tasks are complete OR the caller indicates that the conversation is over. "
                "Farewell message will be supplied to you with this function.",
                schema=end_call_schema,
            ),
            _definition(
                name="escalate_to_human",
                description="Escalate the conversation to a human staff when: "
                "1. Caller wants to speak directly with the staff. "
                "2. Caller has special requests or repeated misunderstandings. "
                "3. Caller's intent is out of your capabilities. "
                "4. Caller wants to place large orders (more than 20 items) or reservations (party size more than 10). "
                "5. If a feature is disabled for this restaurant, include feature_disabled as one of: orders, reservations, faqs.",
                schema=escalate_schema,
            ),
        ]
    )

    # Add SMS redirect function if enabled for orders or reservations
    if sms_redirect_enabled:
        sms_redirect_schema = conversation.SendSMSRedirectArgs.model_json_schema()
        definitions.append(
            _definition(
                name="send_sms_redirect",
                description=(
                    "Send SMS with ordering/reservation link to caller. "
                    "Call SILENTLY as your very first action when customer wants to order or book — "
                    "do NOT speak or narrate before calling. No 'let me send you a link' or similar. "
                    "After it returns, speak naturally using the returned message_to_customer content. "
                    "Restaurant and phone number are automatic from context — only specify redirect_type."
                ),
                schema=sms_redirect_schema,
            )
        )

    return definitions
