import json
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.utils.utc_json_response import UTCJSONResponse


def test_utc_json_response_renders_utc_z():
    content = {
        "ts": datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        "amount": Decimal("3.5"),
        "date": date(2024, 1, 1),
        "time": time(9, 15, 0),
    }
    response = UTCJSONResponse(content=content)
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["ts"] == "2024-01-01T08:00:00Z"
    assert payload["amount"] == 3.5
    assert payload["date"] == "2024-01-01"
    assert payload["time"] == "09:15:00"
