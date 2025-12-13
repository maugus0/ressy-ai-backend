import json
from typing import Any, Dict


def normalize_permissions(routes: Any) -> list[str]:
    """
    Normalize stored permission routes into a list of strings.
    Accepts JSON-encoded strings, plain strings, or lists.
    """
    if routes is None:
        return []
    if isinstance(routes, list):
        return [str(r) for r in routes]
    if isinstance(routes, str):
        try:
            parsed = json.loads(routes)
            if isinstance(parsed, list):
                return [str(p) for p in parsed]
        except json.JSONDecodeError:
            pass
        return [routes]
    return [str(routes)]


def apply_permission_normalization(row: Dict[str, Any]) -> Dict[str, Any]:
    """Attach normalized permissions to a DB row dict."""
    if not row:
        return row
    row["permissions"] = normalize_permissions(row.get("permissions"))
    return row
