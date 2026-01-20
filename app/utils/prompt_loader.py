import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils import prompt_builder


def _read_prompt_file() -> str:
    file_path = os.getenv("DEEPGRAM_THINK_PROMPT_FILE")
    if not file_path:
        return ""
    path = Path(file_path).expanduser().resolve()
    return path.read_text(encoding="utf-8").strip()


def load_think_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """Return the agent prompt, optionally embedding structured context."""

    raw_prompt = _read_prompt_file()
    context_payload = context or {}

    def _default_serializer(value: Any):
        if isinstance(value, Decimal):
            return float(value)
        return str(value)

    try:
        template = json.loads(raw_prompt)
        if isinstance(template, dict):
            if "prompt_template" in template:
                prompt = prompt_builder.build_prompt_from_template(template, context_payload)
                context_for_prompt = dict(context_payload)
                context_for_prompt.pop("agent_capabilities", None)
                prompt["runtime_context"] = context_for_prompt
                return json.dumps(prompt, ensure_ascii=False, default=_default_serializer)
            if context:
                template["runtime_context"] = context_payload
                return json.dumps(template, ensure_ascii=False, default=_default_serializer)
    except json.JSONDecodeError:
        pass

    if not context_payload:
        return raw_prompt

    context_blob = json.dumps(context_payload, ensure_ascii=False, default=_default_serializer)
    return f"{raw_prompt}\n\nRUNTIME_CONTEXT:\n{context_blob}"
