"""Build function definitions for the Deepgram agent from our Pydantic arg models.

The Voice Agent expects a list of function definitions with JSON Schema so the LLM
knows how to call them. We derive the schemas from our arg models to keep things
in sync.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .functions import conversation, menu, orders, reservations, spam_detection


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

    create_order_schema = orders.CreateOrderArgs.model_json_schema()
    lookup_order_schema = orders.LookupOrderArgs.model_json_schema()
    lookup_order_by_id_schema = orders.LookupOrderByIdArgs.model_json_schema()
    create_res_schema = reservations.CreateReservationArgs.model_json_schema()
    update_res_schema = reservations.UpdateReservationArgs.model_json_schema()
    lookup_res_schema = reservations.LookupReservationArgs.model_json_schema()
    check_items_schema = orders.CheckItemsAvailabilityArgs.model_json_schema()
    res_check_avail_schema = reservations.CheckAvailabilityArgs.model_json_schema()
    update_order_details_schema = orders.UpdateOrderDetailsArgs.model_json_schema()
    menu_item_details_schema = menu.GetMenuItemDetailsArgs.model_json_schema()
    # filler_schema = conversation.AgentFillerArgs.model_json_schema()
    end_call_schema = conversation.EndCallArgs.model_json_schema()
    escalate_schema = conversation.EscalateToHumanArgs.model_json_schema()
    detect_spam_schema = spam_detection.DetectSpamBehaviorArgs.model_json_schema()

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
                        "(e.g., 'What's the status of order 12345?'). Requires order_id, restaurant_id, and customer_contact "
                        "(phone number) to verify the order belongs to the caller and restaurant."
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
                    "Retrieve price/description/prep-time details for a specific menu item by item_id, OR search the restaurant menu by search_term. "
                    "For searching, use the base form of the main food item keyword (e.g., convert plurals to singulars like 'tacos' → 'taco', and remove size/flavor modifiers like 'large spicy chicken tacos' → 'chicken taco'). "
                    "IMPORTANT: For general menu browsing or listing categories, answer directly from the menu context provided in your system prompt. "
                    "Only use this function when customer asks for specific details (price, description, prep time) about ONE specific item."
                ),
                schema=menu_item_details_schema,
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
                        "Update the latest reservation for a caller. Requires customer_contact (phone number). "
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
            _definition(
                name="detect_spam_behavior",
                description="IMMEDIATELY call this function if you detect spam or non-human behavior during the call. "
                "Indicators include: immediate perfectly-timed DTMF tones, no background noise, pre-recorded loops, "
                "repetitive non-conversational patterns, or any behavior that suggests this is not a genuine human caller. "
                "This function will create a notification for the restaurant admin to review and will disconnect the call. "
                "You do NOT mark the user as spam - only restaurant admins can do that after reviewing the notification.",
                schema=detect_spam_schema,
            ),
        ]
    )

    return definitions
