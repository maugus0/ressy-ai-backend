import uuid
from datetime import datetime, timezone

from app.utils.timezone import isoformat_z


def generate_id():
    return str(uuid.uuid4())


def get_current_time():
    return isoformat_z(datetime.now(timezone.utc))
