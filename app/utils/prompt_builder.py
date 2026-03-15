from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List


def _normalize_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _join_with_or(values: Iterable[str]) -> str:
    items = [item for item in values if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} or {items[1]}"
    return f"{', '.join(items[:-1])}, or {items[-1]}"


def _build_capabilities_block(template: Dict[str, Any], feature_flags: Dict[str, Any]) -> Dict[str, str]:
    fields = template.get("fields", [])
    capabilities: Dict[str, str] = {}
    for field in fields:
        field_id = field.get("id")
        label = field.get("label") or field_id
        enabled = feature_flags.get(field_id, True)

        # Check for SMS redirect - show as "SMS_REDIRECT" instead of "NO"
        sms_redirect_key = f"{field_id}_sms_redirect"
        sms_redirect_enabled = feature_flags.get(sms_redirect_key, False)

        if enabled:
            capabilities[label] = "YES"
        elif sms_redirect_enabled:
            capabilities[label] = "SMS_REDIRECT (agent cannot take this directly — must use SMS redirect link)"
        else:
            capabilities[label] = "NO"
    return capabilities


def _build_intent_sentence(template: Dict[str, Any], feature_flags: Dict[str, bool]) -> str:
    intent_options = template.get("intent_options", {})
    fallback = template.get("intent_options_fallback", "request assistance from staff")
    options = []
    for key in ("orders", "reservations", "faqs"):
        if feature_flags.get(key, True):
            option = intent_options.get(key)
            if option:
                options.append(option)
    return _join_with_or(options) or fallback


def _build_intent_short(template: Dict[str, Any], feature_flags: Dict[str, bool]) -> str:
    intent_short_options = template.get("intent_short_options", {})
    fallback = template.get("intent_short_fallback", "staff assistance")
    options = []
    for key in ("orders", "reservations", "faqs"):
        if feature_flags.get(key, True):
            option = intent_short_options.get(key)
            if option:
                options.append(option)
    return _join_with_or(options) or fallback


def _build_feature_flags(context: Dict[str, Any]) -> Dict[str, Any]:
    """Build feature flags including SMS redirect from agent_capabilities context."""
    capabilities = context.get("agent_capabilities", {}) if isinstance(context, dict) else {}
    orders_cap = capabilities.get("orders", {})
    reservations_cap = capabilities.get("reservations", {})
    faqs_cap = capabilities.get("faqs", {})

    orders_sms = orders_cap.get("sms_redirect", {}) if isinstance(orders_cap, dict) else {}
    reservations_sms = reservations_cap.get("sms_redirect", {}) if isinstance(reservations_cap, dict) else {}

    return {
        "orders": _normalize_bool(orders_cap.get("enabled") if isinstance(orders_cap, dict) else orders_cap, True),
        "reservations": _normalize_bool(
            reservations_cap.get("enabled") if isinstance(reservations_cap, dict) else reservations_cap, True
        ),
        "faqs": _normalize_bool(faqs_cap.get("enabled") if isinstance(faqs_cap, dict) else faqs_cap, True),
        "orders_sms_redirect": _normalize_bool(orders_sms.get("enabled"), False),
        "reservations_sms_redirect": _normalize_bool(reservations_sms.get("enabled"), False),
    }


def build_prompt_from_template(template: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    prompt_template = template.get("prompt_template", {})
    base = deepcopy(prompt_template.get("base", {}))
    feature_modules = prompt_template.get("feature_modules", {})

    feature_flags = _build_feature_flags(context)
    orders_enabled = feature_flags.get("orders", True)
    reservations_enabled = feature_flags.get("reservations", True)
    faqs_enabled = feature_flags.get("faqs", True)

    agent_identity = deepcopy(base.get("agent_identity", {}))
    base_goals = list(agent_identity.get("primary_goals", []))
    feature_goals: List[str] = []
    if orders_enabled:
        feature_goals.extend(feature_modules.get("orders", {}).get("primary_goals", []))
    if reservations_enabled:
        feature_goals.extend(feature_modules.get("reservations", {}).get("primary_goals", []))
    if faqs_enabled:
        feature_goals.extend(feature_modules.get("faqs", {}).get("primary_goals", []))
    if feature_goals:
        agent_identity["primary_goals"] = base_goals + feature_goals
    else:
        agent_identity["primary_goals"] = base_goals

    capabilities_template = prompt_template.get("capabilities_block_template", {})
    capabilities = _build_capabilities_block(capabilities_template, feature_flags)

    handoff_rules = list(prompt_template.get("handoff_rules_template", []))
    disabled_rules_template = prompt_template.get("disabled_feature_rules_template", {})
    orders_sms_redirect = feature_flags.get("orders_sms_redirect", False)
    reservations_sms_redirect = feature_flags.get("reservations_sms_redirect", False)

    # Handle orders: escalate if disabled AND no SMS redirect
    if not orders_enabled:
        if orders_sms_redirect:
            handoff_rules.append(
                "ORDERING: When customer wants to order, silently call send_sms_redirect(redirect_type='orders') "
                "as your very next action. Do NOT say anything before calling the function — no narration, "
                "no explanation, no 'let me send you a link'. Just call the function in silence. "
                "After it returns, speak using the message_to_customer content. "
                "Never collect items, quantities, or customizations. Never call create_order or update_order_details."
            )
        else:
            disabled_rule = disabled_rules_template.get("orders")
            if disabled_rule:
                handoff_rules.append(disabled_rule)

    # Handle reservations: escalate if disabled AND no SMS redirect
    if not reservations_enabled:
        if reservations_sms_redirect:
            handoff_rules.append(
                "RESERVATIONS: When customer wants to book a table, silently call send_sms_redirect(redirect_type='reservations') "
                "as your very next action. Do NOT say anything before calling the function — no narration, "
                "no explanation, no 'let me send you a link'. Just call the function in silence. "
                "After it returns, speak using the message_to_customer content. "
                "Never collect party size, dates, or times. Never call create_reservation or check_reservation_availability."
            )
        else:
            disabled_rule = disabled_rules_template.get("reservations")
            if disabled_rule:
                handoff_rules.append(disabled_rule)

    if not faqs_enabled:
        disabled_rule = disabled_rules_template.get("faqs")
        if disabled_rule:
            handoff_rules.append(disabled_rule)

    # When any SMS redirect is active, remind the agent to mention transfer option
    if orders_sms_redirect or reservations_sms_redirect:
        handoff_rules.append(
            "When SMS redirect is active, proactively remind callers they can say 'transfer' or 'escalate' "
            "to reach the team at any time. This should feel natural and reassuring, not robotic."
        )

    # Escalation mode awareness
    restaurant_profile = context.get("restaurant_profile", {}) if isinstance(context, dict) else {}
    escalation_mode = restaurant_profile.get("escalation_mode", "always")
    is_open_now = restaurant_profile.get("is_open_now", True)
    if escalation_mode == "open_hours_only" and not is_open_now:
        handoff_rules.append(
            "The restaurant is currently closed. If the caller asks to be transferred or escalated, "
            "inform them that the team is not available right now, provide the operating hours, "
            "and offer to help with any questions you can answer. You may still call escalate_to_human — "
            "the system will handle the response appropriately."
        )

    call_flow_base = deepcopy(prompt_template.get("call_flow_base", {}))
    intent_sentence = _build_intent_sentence(prompt_template, feature_flags)
    intent_short = _build_intent_short(prompt_template, feature_flags)
    intent_template = prompt_template.get("intent_determination_template")
    if intent_template:
        call_flow_base["intent_determination"] = intent_template.format(intent_options=intent_sentence)

    info_template = prompt_template.get("information_order_template", [])
    information_order = []
    for item in info_template:
        if isinstance(item, str):
            information_order.append(item.format(intent_short=intent_short))
    if information_order:
        call_flow_base["information_order"] = information_order

    if orders_enabled:
        orders_flow = feature_modules.get("orders", {}).get("call_flow", {})
        call_flow_base.update(deepcopy(orders_flow))
    if reservations_enabled:
        reservations_flow = feature_modules.get("reservations", {}).get("call_flow", {})
        call_flow_base.update(deepcopy(reservations_flow))

    feature_rules: List[str] = []
    if orders_enabled:
        feature_rules.extend(feature_modules.get("orders", {}).get("feature_rules", []))
    if reservations_enabled:
        feature_rules.extend(feature_modules.get("reservations", {}).get("feature_rules", []))
    if faqs_enabled:
        feature_rules.extend(feature_modules.get("faqs", {}).get("feature_rules", []))

    prompt: Dict[str, Any] = {}
    if agent_identity:
        prompt["agent_identity"] = agent_identity
    if "tone_and_style" in base:
        prompt["tone_and_style"] = deepcopy(base["tone_and_style"])
    if capabilities:
        prompt["capabilities"] = capabilities
    if handoff_rules:
        prompt["handoff_rules"] = handoff_rules
    if call_flow_base:
        prompt["call_flow"] = call_flow_base
    if feature_rules:
        prompt["feature_rules"] = feature_rules
    if "general_rules" in base:
        prompt["general_rules"] = deepcopy(base["general_rules"])
    if "service_rules" in base:
        prompt["service_rules"] = deepcopy(base["service_rules"])

    restaurant_specific = context.get("restaurant_specific_instructions")
    if restaurant_specific:
        prompt["restaurant_specific_instructions"] = restaurant_specific

    return prompt
