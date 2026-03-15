import json
from pathlib import Path

from app.utils import prompt_builder


def _load_template() -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    prompt_path = repo_root / "prompts" / "dg_context_prompt.json"
    return json.loads(prompt_path.read_text(encoding="utf-8"))


def test_prompt_builder_all_enabled():
    template = _load_template()
    context = {
        "agent_capabilities": {
            "orders": {"enabled": True},
            "reservations": {"enabled": True},
            "faqs": {"enabled": True},
        }
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)

    assert "order_flow" in prompt["call_flow"]
    assert "reservation_flow" in prompt["call_flow"]
    assert prompt["capabilities"]["Take pickup orders"] == "YES"
    assert prompt["capabilities"]["Manage reservations"] == "YES"
    assert prompt["capabilities"]["Answer FAQs"] == "YES"
    handoff_text = " ".join(prompt["handoff_rules"])
    assert "orders_disabled" not in handoff_text
    assert "reservations_disabled" not in handoff_text
    assert "faqs_disabled" not in handoff_text


def test_prompt_builder_faqs_only():
    template = _load_template()
    context = {
        "agent_capabilities": {
            "orders": {"enabled": False},
            "reservations": {"enabled": False},
            "faqs": {"enabled": True},
        }
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)

    assert "order_flow" not in prompt["call_flow"]
    assert "reservation_flow" not in prompt["call_flow"]
    assert "orders_disabled" in " ".join(prompt["handoff_rules"])
    assert "reservations_disabled" in " ".join(prompt["handoff_rules"])
    assert prompt["capabilities"]["Take pickup orders"] == "NO"
    assert prompt["capabilities"]["Manage reservations"] == "NO"
    assert prompt["capabilities"]["Answer FAQs"] == "YES"
    assert all("pickup order" not in goal for goal in prompt["agent_identity"]["primary_goals"])


def test_prompt_builder_skips_empty_restaurant_instructions():
    template = _load_template()
    context = {"agent_capabilities": {"orders": {"enabled": True}}}
    prompt = prompt_builder.build_prompt_from_template(template, context)

    assert "restaurant_specific_instructions" not in prompt


def test_prompt_builder_includes_restaurant_instructions():
    template = _load_template()
    context = {
        "agent_capabilities": {"orders": {"enabled": True}},
        "restaurant_specific_instructions": {"cuisine_rules": ["Confirm spice level."]},
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)

    assert "restaurant_specific_instructions" in prompt


def test_sms_redirect_adds_transfer_reminder():
    """When SMS redirect is active, a transfer/escalate reminder handoff rule is added."""
    template = _load_template()
    context = {
        "agent_capabilities": {
            "orders": {"enabled": False, "orders_sms_redirect": True},
            "reservations": {"enabled": True},
            "faqs": {"enabled": True},
        }
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)
    handoff_text = " ".join(prompt["handoff_rules"])
    assert "transfer" in handoff_text.lower()
    assert "escalate" in handoff_text.lower()


def test_sms_redirect_absent_no_transfer_reminder():
    """When no SMS redirect is active, the transfer reminder rule is absent."""
    template = _load_template()
    context = {
        "agent_capabilities": {
            "orders": {"enabled": True},
            "reservations": {"enabled": True},
            "faqs": {"enabled": True},
        }
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)
    handoff_text = " ".join(prompt["handoff_rules"])
    assert "SMS redirect is active" not in handoff_text


def test_escalation_mode_open_hours_only_closed():
    """When escalation_mode=open_hours_only and restaurant is closed, a closed-hours rule is added."""
    template = _load_template()
    context = {
        "agent_capabilities": {
            "orders": {"enabled": True},
            "reservations": {"enabled": True},
            "faqs": {"enabled": True},
        },
        "restaurant_profile": {
            "escalation_mode": "open_hours_only",
            "is_open_now": False,
        },
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)
    handoff_text = " ".join(prompt["handoff_rules"])
    assert "currently closed" in handoff_text


def test_escalation_mode_always_no_closed_rule():
    """When escalation_mode=always, no closed-hours rule is added even if restaurant is closed."""
    template = _load_template()
    context = {
        "agent_capabilities": {
            "orders": {"enabled": True},
            "reservations": {"enabled": True},
            "faqs": {"enabled": True},
        },
        "restaurant_profile": {
            "escalation_mode": "always",
            "is_open_now": False,
        },
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)
    handoff_text = " ".join(prompt["handoff_rules"])
    assert "currently closed" not in handoff_text


def test_escalation_mode_open_hours_only_open():
    """When escalation_mode=open_hours_only but restaurant is open, no closed-hours rule."""
    template = _load_template()
    context = {
        "agent_capabilities": {
            "orders": {"enabled": True},
            "reservations": {"enabled": True},
            "faqs": {"enabled": True},
        },
        "restaurant_profile": {
            "escalation_mode": "open_hours_only",
            "is_open_now": True,
        },
    }
    prompt = prompt_builder.build_prompt_from_template(template, context)
    handoff_text = " ".join(prompt["handoff_rules"])
    assert "currently closed" not in handoff_text
