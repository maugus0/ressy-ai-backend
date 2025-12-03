"""Helper dataclasses for richer agent function responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AgentSideEffect:
    """Represents a message emitted after a function response (e.g., InjectAgentMessage)."""

    payload: Dict[str, Any]
    delay_seconds: float = 0.0


@dataclass
class AgentFunctionResult:
    """Wrapper for returning both function content and optional side effects."""

    content: Dict[str, Any]
    side_effects: List[AgentSideEffect] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.content
