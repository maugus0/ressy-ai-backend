import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional


def _read_prompt_file() -> str:
    file_path = os.getenv("DEEPGRAM_THINK_PROMPT_FILE")
    if not file_path:
        return ""
    path = Path(file_path).expanduser().resolve()
    return path.read_text(encoding="utf-8").strip()


def load_think_prompt(context: Optional[Dict[str, Any]] = None) -> str:
    """Return the agent prompt, optionally embedding structured context."""

    raw_prompt = _read_prompt_file()
    if not context:
        return raw_prompt

    def _default_serializer(value: Any):
        if isinstance(value, Decimal):
            return float(value)
        return str(value)

    try:
        template = json.loads(raw_prompt)
        if isinstance(template, dict):
            template["dynamic_context"] = context
            return json.dumps(template, ensure_ascii=False, default=_default_serializer)
    except json.JSONDecodeError:
        pass

    context_blob = json.dumps(context, ensure_ascii=False, default=_default_serializer)
    return f"{raw_prompt}\n\nDYNAMIC_CONTEXT:\n{context_blob}"
