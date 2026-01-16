from __future__ import annotations

import json
from typing import Any

from starlette.responses import JSONResponse

from app.utils.timezone import json_default


class UTCJSONResponse(JSONResponse):
    """JSONResponse that renders datetimes as UTC ISO 8601 with Z."""

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            default=json_default,
        ).encode("utf-8")
